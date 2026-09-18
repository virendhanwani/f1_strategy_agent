import asyncio
from agents.pit_strategy_tool import analyze_race_strategy

async def main():
    result = await analyze_race_strategy("2023", "6")  # Monaco
    print(result["race_name"])
    for line in result["summary"]:
        print(" ", line)

asyncio.run(main())