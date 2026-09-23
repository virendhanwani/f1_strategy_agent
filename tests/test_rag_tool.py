import asyncio
from agents.rules_rag_tool import answer_regulation_question

async def main():
    result = await answer_regulation_question("how many mandatory pit stops are required in a dry race")
    if "error" in result:
        print(result["error"], result["hint"])
        return
    print("Regulation year:", result["regulation_year"])
    print(result["answer"])
    print("\nSources:", result["sources"])

if __name__ == "__main__":
    asyncio.run(main())
