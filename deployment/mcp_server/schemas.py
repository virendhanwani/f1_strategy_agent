"""
Typed models for F1 data, flattened from Jolpica's nested MRData JSON shape.
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class Driver(BaseModel):
    driver_id: str
    permanent_number: str
    code: Optional[str] = None
    given_name: str
    family_name: str
    nationality: Optional[str] = None


class Constructor(BaseModel):
    constructor_id: str
    name: str
    nationality: Optional[str] = None


class RaceResult(BaseModel):
    position: int
    points: float
    driver: Driver
    constructor: Constructor
    grid: int
    laps: int
    status: str
    time: Optional[str] = None  # finishing time gap, e.g. "+1.234", only set for classified finishers


class RaceResultsResponse(BaseModel):
    season: str
    round: str
    race_name: str
    date: str
    results: list[RaceResult]


class QualifyingResult(BaseModel):
    position: int
    driver: Driver
    constructor: Constructor
    q1: Optional[str] = None
    q2: Optional[str] = None
    q3: Optional[str] = None


class QualifyingResponse(BaseModel):
    season: str
    round: str
    race_name: str
    date: str
    results: list[QualifyingResult]


class PitStop(BaseModel):
    driver_id: str
    lap: int
    stop: int
    time: str       # time of day the stop happened, e.g. "14:23:15"
    duration: str    # stop duration, e.g. "2.345"


class PitStopsResponse(BaseModel):
    season: str
    round: str
    race_name: str
    pit_stops: list[PitStop]


class DriverStanding(BaseModel):
    position: int
    points: float
    wins: int
    driver: Driver
    constructors: list[Constructor]


class ConstructorStanding(BaseModel):
    position: int
    points: float
    wins: int
    constructor: Constructor


class DriverStandingsResponse(BaseModel):
    season: str
    standings: list[DriverStanding]


class ConstructorStandingsResponse(BaseModel):
    season: str
    standings: list[ConstructorStanding]


class LapTiming(BaseModel):
    driver_id: str
    position: int
    time: Optional[str] = None  # lap time, e.g. "1:12.345"


class Lap(BaseModel):
    number: int
    timings: list[LapTiming]


class LapTimesResponse(BaseModel):
    season: str
    round: str
    race_name: str
    laps: list[Lap]


class DriverInfo(BaseModel):
    driver_id: str
    code: Optional[str] = None          # 3-letter code, e.g. "VER"
    permanent_number: Optional[str] = None
    given_name: str
    family_name: str
    date_of_birth: str
    nationality: Optional[str] = None


class CircuitInfo(BaseModel):
    circuit_id: str
    circuit_name: str
    locality: Optional[str] = None
    country: Optional[str] = None
    lat: Optional[float] = None
    long: Optional[float] = None


class RaceScheduleEntry(BaseModel):
    round: str
    race_name: str
    date: str
    time: Optional[str] = None
    circuit: CircuitInfo


class RaceScheduleResponse(BaseModel):
    season: str
    races: list[RaceScheduleEntry]
