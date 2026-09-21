import asyncio
from agents.rules_rag_tool import answer_regulation_question

async def main():
    result = await answer_regulation_question("how many mandatory pit stops are required in a dry race")
    print(result["answer"])
    print("\nSources:", result["sources"])

asyncio.run(main())