import asyncio
from agents.telemetry_tool import get_tire_strategy, compare_pace

async def main():
    result = await get_tire_strategy(2023, "Monaco", "VER")
    for stint in result["stints"]:
        print(stint)

    comp = await compare_pace(2023, "Monaco", ["VER", "HAM", "ALO"])
    print(comp["comparison"])

asyncio.run(main())