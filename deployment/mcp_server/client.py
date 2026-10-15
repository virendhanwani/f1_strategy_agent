"""
Async wrapper around the Jolpica-F1 API.

Docs: https://github.com/jolpica/jolpica-f1/blob/main/docs/README.md
Base URL: https://api.jolpi.ca/ergast/f1
"""

from __future__ import annotations
import difflib
import asyncio
import logging
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Optional
import httpx

from schemas import (
    Driver,
    Constructor,
    RaceResult,
    RaceResultsResponse,
    QualifyingResult,
    QualifyingResponse,
    PitStop,
    PitStopsResponse,
    DriverStanding,
    ConstructorStanding,
    DriverStandingsResponse,
    ConstructorStandingsResponse,
    LapTiming,
    Lap,
    LapTimesResponse,
    DriverInfo,
    CircuitInfo,
    RaceScheduleEntry,
    RaceScheduleResponse
)

BASE_URL = "https://api.jolpi.ca/ergast/f1"
logger = logging.getLogger(__name__)

def _normalize(name: str) -> str:
    """Loosely normalize a race/circuit name for matching, e.g.
    'Monaco GP' and 'Monaco Grand Prix' should both become 'monaco'."""
    name = name.lower().strip()
    for suffix in ("grand prix", "gp"):
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
    return name

def _driver(raw: dict) -> Driver:
    return Driver(
        driver_id=raw["driverId"],
        permanent_number=raw["permanentNumber"],
        code=raw.get("code"),
        given_name=raw["givenName"],
        family_name=raw["familyName"],
        nationality=raw.get("nationality"),
    )

def _constructor(raw: dict) -> Constructor:
    return Constructor(
        constructor_id=raw["constructorId"],
        name=raw["name"],
        nationality=raw.get("nationality"),
    )

def _circuit(raw: dict) -> CircuitInfo:
    loc = raw.get("Location", {})
    return CircuitInfo(
        circuit_id=raw["circuitId"],
        circuit_name=raw["circuitName"],
        locality=loc.get("locality"),
        country=loc.get("country"),
        lat=float(loc["lat"]) if loc.get("lat") else None,
        long=float(loc["long"]) if loc.get("long") else None,
    )

def _normalize_name(name: str) -> str:
    """Generic lowercase/strip normalization for driver and circuit name matching."""
    return name.lower().strip()

class JolpicaClient:
    """Async client for the Jolpica-F1 API. Use as an async context manager."""

    def __init__(self, base_url: str = BASE_URL, timeout: float = 15.0):
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=timeout,
            headers={"User-Agent": "f1-mcp/0.1.0"},
        )
        self._request_lock = asyncio.Lock()
        self._next_request_at = 0.0
        self._schedule_cache: dict[str, list[dict]] = {} 
        self._driver_cache: dict[str, list[dict]] = {}
        self._circuit_cache: list[dict] | None = None

    async def __aenter__(self) -> "JolpicaClient":
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        params = {"limit": 100, **(params or {})}  # default 100, but allow override per-call
        # Share pacing and cooldown across concurrent tools and pagination.
        async with self._request_lock:
            for attempt in range(4):  # initial request + at most three retries
                wait = max(0, self._next_request_at - time.monotonic())
                if wait > 20:
                    raise RuntimeError(
                        f"Jolpica is still rate limited. Retry after at least {wait:.0f} seconds."
                    )
                await asyncio.sleep(wait)
                self._next_request_at = time.monotonic() + 0.3
                resp = await self._client.get(path, params=params)
                if resp.status_code != 429:
                    resp.raise_for_status()
                    return resp.json()["MRData"]

                delay = self._retry_delay(resp.headers.get("Retry-After"), attempt)
                self._next_request_at = max(self._next_request_at, time.monotonic() + delay)
                # Do not shorten the upstream cooldown to fit our retry budget.
                if attempt == 3 or delay > 20:
                    raise RuntimeError(
                        "Jolpica rate limit reached. "
                        f"Retry after at least {delay:.0f} seconds; "
                        "the API may have reached its hourly quota."
                    ) from None
                logger.warning("Jolpica rate limited; retry %s/3 in %.1fs", attempt + 1, delay)

    @staticmethod
    def _retry_delay(retry_after: str | None, attempt: int) -> float:
        """Accept Retry-After seconds or an HTTP date; otherwise back off."""
        if retry_after:
            try:
                return max(0.0, float(int(retry_after)))
            except ValueError:
                try:
                    retry_date = parsedate_to_datetime(retry_after)
                    if retry_date.tzinfo is None:
                        retry_date = retry_date.replace(tzinfo=timezone.utc)
                    return max(0.0, (retry_date - datetime.now(timezone.utc)).total_seconds())
                except (TypeError, ValueError, OverflowError):
                    pass
        return float(2 ** (attempt + 1))

    async def _get_page(self, path: str, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        return await self._get(path, params={"limit": limit, "offset": offset})


    async def _get_race_paginated(self, path: str, list_key: str, merge_by_lap: bool = False) -> dict:
        """
        Paginates a /{season}/{round}/<endpoint>.json call whose data lives at
        RaceTable.Races[0][list_key] — the shape shared by results, qualifying,
        pitstops, and laps. All of these CAN exceed Jolpica's 100-item page limit
        for busy races (laps: ~20 drivers x ~70 laps = 1400+ timing entries;
        pit stops: a wet race with many stops per car can also exceed 100).

        merge_by_lap=True is needed specifically for /laps.json, since pages can
        split a single lap's driver timings across page boundaries — items need
        to be merged INTO the right lap entry, not just concatenated.
        """
        limit = 100
        offset = 0
        race_meta: dict | None = None
        merged_items: list = []
        lap_index: dict[int, dict] = {}

        while True:
            data = await self._get_page(path, limit=limit, offset=offset)
            races = data["RaceTable"]["Races"]
            if not races:
                break
            race = races[0]
            if race_meta is None:
                race_meta = {k: v for k, v in race.items() if k != list_key}

            page_items = race.get(list_key, [])

            if merge_by_lap:
                for lap in page_items:
                    lap_num = int(lap["number"])
                    lap_index.setdefault(lap_num, {"number": lap["number"], "Timings": []})
                    lap_index[lap_num]["Timings"].extend(lap["Timings"])
            else:
                merged_items.extend(page_items)

            total = int(data["total"])
            offset += limit
            if offset >= total:
                break

        if merge_by_lap:
            merged_items = [lap_index[n] for n in sorted(lap_index)]

        if race_meta is None:
            raise ValueError(f"No race data found for path={path}")

        race_meta[list_key] = merged_items
        return race_meta
    # ---- Results ----------------------------------------------------

    async def get_race_results(self, season: str, round_: str = "last") -> RaceResultsResponse:
        race = await self._get_race_paginated(f"/{season}/{round_}/results.json", "Results")
        results = [
            RaceResult(
                position=int(r["position"]), points=float(r["points"]),
                driver=_driver(r["Driver"]), constructor=_constructor(r["Constructor"]),
                grid=int(r["grid"]), laps=int(r["laps"]), status=r["status"],
                time=r.get("Time", {}).get("time"),
            )
            for r in race["Results"]
        ]
        return RaceResultsResponse(season=race["season"], round=race["round"], race_name=race["raceName"], date=race["date"], results=results)

    # ---- Qualifying ---------------------------------------------------

    async def get_qualifying(self, season: str, round_: str = "last") -> QualifyingResponse:
        race = await self._get_race_paginated(f"/{season}/{round_}/qualifying.json", "QualifyingResults")
        results = [
            QualifyingResult(
                position=int(q["position"]), driver=_driver(q["Driver"]), constructor=_constructor(q["Constructor"]),
                q1=q.get("Q1"), q2=q.get("Q2"), q3=q.get("Q3"),
            )
            for q in race["QualifyingResults"]
        ]
        return QualifyingResponse(season=race["season"], round=race["round"], race_name=race["raceName"], date=race["date"], results=results)

    # ---- Pit stops ----------------------------------------------------

    async def get_pit_stops(self, season: str, round_: str) -> PitStopsResponse:
        race = await self._get_race_paginated(f"/{season}/{round_}/pitstops.json", "PitStops")
        stops = [
            PitStop(driver_id=p["driverId"], lap=int(p["lap"]), stop=int(p["stop"]), time=p["time"], duration=p["duration"])
            for p in race.get("PitStops", [])
        ]
        return PitStopsResponse(season=race["season"], round=race["round"], race_name=race["raceName"], pit_stops=stops)


    # ---- Standings ------------------------------------------------------

    async def get_driver_standings(self, season: str = "current") -> DriverStandingsResponse:
        data = await self._get(f"/{season}/driverStandings.json")
        lists = data["StandingsTable"]["StandingsLists"]
        if not lists:
            raise ValueError(f"No driver standings found for season={season}")
        standings_list = lists[0]

        standings = [
            DriverStanding(
                position=int(s["position"]),
                points=float(s["points"]),
                wins=int(s["wins"]),
                driver=_driver(s["Driver"]),
                constructors=[_constructor(c) for c in s["Constructors"]],
            )
            for s in standings_list["DriverStandings"]
        ]
        return DriverStandingsResponse(season=standings_list["season"], standings=standings)

    async def get_constructor_standings(self, season: str = "current") -> ConstructorStandingsResponse:
        data = await self._get(f"/{season}/constructorStandings.json")
        lists = data["StandingsTable"]["StandingsLists"]
        if not lists:
            raise ValueError(f"No constructor standings found for season={season}")
        standings_list = lists[0]

        standings = [
            ConstructorStanding(
                position=int(s["position"]),
                points=float(s["points"]),
                wins=int(s["wins"]),
                constructor=_constructor(s["Constructor"]),
            )
            for s in standings_list["ConstructorStandings"]
        ]
        return ConstructorStandingsResponse(season=standings_list["season"], standings=standings)

    async def get_race_schedule(self, season: str) -> list[dict]:
        """Raw race calendar for a season — cached, since name lookups reuse it."""
        if season not in self._schedule_cache:
            data = await self._get(f"/{season}.json")
            self._schedule_cache[season] = data["RaceTable"]["Races"]
        return self._schedule_cache[season]

    async def _resolve_round(self, season: str, race_name: str) -> str:
        races = await self.get_race_schedule(season)
        target = _normalize(race_name)

        # pass 1: substring match against race name, circuit name, or locality
        for race in races:
            candidates = [
                race["raceName"],
                race["Circuit"]["circuitName"],
                race["Circuit"]["Location"].get("locality", ""),
            ]
            if any(target in _normalize(c) or _normalize(c) in target for c in candidates):
                return race["round"]

        # pass 2: fuzzy fallback, e.g. typos or unusual nicknames
        names = [_normalize(r["raceName"]) for r in races]
        match = difflib.get_close_matches(target, names, n=1, cutoff=0.4)
        if match:
            return races[names.index(match[0])]["round"]

        raise ValueError(f"No race matching '{race_name}' found in season {season}")

    async def get_race_results_by_name(self, season: str, race_name: str) -> RaceResultsResponse:
        round_ = await self._resolve_round(season, race_name)
        return await self.get_race_results(season, round_)

# ---- Lap times ------------------------------------------------------

    async def get_lap_times(self, season: str, round_: str, driver_id: Optional[str] = None) -> LapTimesResponse:
        path = f"/{season}/{round_}/laps.json" if not driver_id else f"/{season}/{round_}/drivers/{driver_id}/laps.json"
        race = await self._get_race_paginated(path, "Laps", merge_by_lap=True)

        laps = []
        skipped = 0
        for lap in race["Laps"]:
            timings = []
            for t in lap["Timings"]:
                try:
                    timings.append(
                        LapTiming(driver_id=t["driverId"], position=int(t["position"]), time=t.get("time"))
                    )
                except (KeyError, ValueError, TypeError):
                    # incomplete entry, typically a driver who retired/crashed
                    skipped += 1
                    continue
            laps.append(Lap(number=int(lap["number"]), timings=timings))

        if skipped:
            print(f"  get_lap_times: skipped {skipped} incomplete timing entries (likely retirements)")

        return LapTimesResponse(season=race["season"], round=race["round"], race_name=race["raceName"], laps=laps)

    async def get_lap_times_by_name(self, season: str, round_: str, driver_name: str) -> LapTimesResponse:
        driver_id = await self.resolve_driver_id(driver_name, season)
        return await self.get_lap_times(season, round_, driver_id)
    # ---- Driver info ------------------------------------------------------

    async def get_driver_info(self, driver_id: str) -> DriverInfo:
        data = await self._get(f"/drivers/{driver_id}.json")
        drivers = data["DriverTable"]["Drivers"]
        if not drivers:
            raise ValueError(f"No driver found for driver_id={driver_id}")
        d = drivers[0]
        return DriverInfo(
            driver_id=d["driverId"],
            code=d.get("code"),
            permanent_number=d.get("permanentNumber"),
            given_name=d["givenName"],
            family_name=d["familyName"],
            date_of_birth=d["dateOfBirth"],
            nationality=d.get("nationality"),
        )

    # ---- Circuit info ------------------------------------------------------

    async def get_circuit_info(self, circuit_id: str) -> CircuitInfo:
        data = await self._get(f"/circuits/{circuit_id}.json")
        circuits = data["CircuitTable"]["Circuits"]
        if not circuits:
            raise ValueError(f"No circuit found for circuit_id={circuit_id}")
        return _circuit(circuits[0])

    # ---- Race schedule ------------------------------------------------------

    async def get_race_schedule_typed(self, season: str) -> RaceScheduleResponse:
        # reuses the same raw-schedule cache that name-resolution already relies on
        races = await self.get_race_schedule(season)
        entries = [
            RaceScheduleEntry(
                round=r["round"],
                race_name=r["raceName"],
                date=r["date"],
                time=r.get("time"),
                circuit=_circuit(r["Circuit"]),
            )
            for r in races
        ]
        return RaceScheduleResponse(season=season, races=entries)

    # ---- Driver name resolution ----------------------------------------------

    async def _fetch_season_drivers(self, season: str) -> list[dict]:
        if season not in self._driver_cache:
            data = await self._get(f"/{season}/drivers.json?limit=100")
            self._driver_cache[season] = data["DriverTable"]["Drivers"]
        return self._driver_cache[season]

    async def resolve_driver_id(self, name: str, season: str = "current") -> str:
        drivers = await self._fetch_season_drivers(season)
        target = _normalize_name(name)

        # pass 1: exact/substring match against id, code, surname, or full name
        for d in drivers:
            candidates = [
                d["driverId"],
                d.get("code", ""),
                d["familyName"],
                f"{d['givenName']} {d['familyName']}",
            ]
            if any(target == _normalize_name(c) or target in _normalize_name(c) for c in candidates if c):
                return d["driverId"]

        # pass 2: fuzzy fallback on surname, for typos
        surnames = [_normalize_name(d["familyName"]) for d in drivers]
        match = difflib.get_close_matches(target, surnames, n=1, cutoff=0.5)
        if match:
            return drivers[surnames.index(match[0])]["driverId"]

        raise ValueError(f"No driver matching '{name}' found in season {season}")

    # ---- Circuit name resolution ----------------------------------------------

    async def _fetch_all_circuits(self) -> list[dict]:
        if self._circuit_cache is None:
            data = await self._get("/circuits.json?limit=100")
            self._circuit_cache = data["CircuitTable"]["Circuits"]
        return self._circuit_cache

    async def resolve_circuit_id(self, name: str) -> str:
        circuits = await self._fetch_all_circuits()
        target = _normalize_name(name)

        for c in circuits:
            candidates = [c["circuitId"], c["circuitName"], c["Location"].get("locality", "")]
            if any(target == _normalize_name(v) or target in _normalize_name(v) for v in candidates if v):
                return c["circuitId"]

        names = [_normalize_name(c["circuitName"]) for c in circuits]
        match = difflib.get_close_matches(target, names, n=1, cutoff=0.4)
        if match:
            return circuits[names.index(match[0])]["circuitId"]

        raise ValueError(f"No circuit matching '{name}' found")

    # ---- Convenience wrappers combining resolve + fetch ----------------------

    async def get_driver_info_by_name(self, name: str, season: str = "current") -> DriverInfo:
        driver_id = await self.resolve_driver_id(name, season)
        return await self.get_driver_info(driver_id)

    async def get_circuit_info_by_name(self, name: str) -> CircuitInfo:
        circuit_id = await self.resolve_circuit_id(name)
        return await self.get_circuit_info(circuit_id)
