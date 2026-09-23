import asyncio
from agents.orchestrator import ask

async def main():
    answer = await ask("What happened in the 2023 Monaco Grand Prix, and were there any interesting pit stop strategies?")
    print(answer)

asyncio.run(main())