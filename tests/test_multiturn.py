import asyncio
from agents.orchestrator import chat


async def main():
    state = await chat("What happened in the 2021 Abu Dhabi finale?")
    print("Q1:", state["messages"][-1].content, "\n")

    state = await chat(
        "Why didn't Mercedes pit Hamilton under that late safety car?",
        history=state["messages"],
    )
    print("Q2:", state["messages"][-1].content)


if __name__ == "__main__":
    asyncio.run(main())
