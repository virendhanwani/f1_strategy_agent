# F1 Strategy Agent

A multi-agent system that answers F1 race-strategy questions by combining
real telemetry data with a RAG layer over the sporting regulations —
evaluated, observable, and served through an API.

Pairs two data sources with deliberately different roles:

- **[f1-mcp](https://github.com/virendhanwani/f1-mcp)** — a standalone MCP server wrapping
  the Jolpica-F1 API (results, qualifying, standings, pit stops, lap times,
  driver/circuit info). Stateless, fast, no session-loading cost — the
  default path for most questions.
- **[FastF1](https://github.com/theOehrly/Fast-F1)** — official timing telemetry: tire compound/age,
  speed/throttle traces, weather, and track status. Stateful and slower to
  load, so it's reserved for questions that genuinely need that depth.

## Why two sources instead of one

Jolpica alone can't answer "why did the tires fall off in that stint" —
it has no telemetry. FastF1 alone is too slow to be the default path for
"who won the 2023 Monaco GP." Splitting them by what they're each good at,
and routing questions to the cheaper source first, is the core design
decision behind this project.

## Project structure

f1-strategy-agent/
├── data/
│ ├── raw/ # FastF1's own on-disk cache
│ └── processed/ # parquet: laps, results, weather per session
├── ingestion/
│ └── fetch_sessions.py # fetches + caches FastF1 sessions
├── analysis/
│ ├── pit_strategy.py # undercut/overcut detection (Jolpica data only)
│ └── telemetry.py # tire degradation, stints, speed traces (FastF1)
├── agents/
│ ├── ergast_mcp_client.py # MCP client connecting to f1-ergast-mcp
│ ├── telemetry_tool.py # wraps telemetry.py as an agent tool — pending
│ ├── strategy_tool.py # wraps pit_strategy.py as an agent tool — pending
│ ├── rules_rag_tool.py # RAG over F1 regulations — pending
│ └── orchestrator.py # LangGraph routing across all tools — pending
├── eval/ # RAG evaluation (ragas) — pending
├── observability/ # Langfuse tracing — pending
├── api/ # FastAPI endpoint — pending
├── dashboard/ # Streamlit UI — pending
├── tests/
├── pyproject.toml
└── uv.lock

## Setup

```bash
uv sync
```

## Running the ingestion pipeline

```bash
uv run python -m ingestion.fetch_sessions
```

Fetches and caches a curated set of strategically interesting races (wet
races, safety-car-heavy races, tight-track races) to `data/processed/` as
parquet.
