import asyncio
from agents.orchestrator import stream_chat


async def main():
    history = []
    for question in [
        "Who won the 2023 Monaco Grand Prix?",
        "Were there any interesting pit stop strategies in that race?",
    ]:
        print("\nQuestion:", question)
        async for event in stream_chat(question, history):
            if event["type"] == "complete":
                history = event["state"]["messages"]
                print("Answer:", event["answer"])
            else:
                print(event["type"], event.get("tool", ""), "-", event["message"])


if __name__ == "__main__":
    asyncio.run(main())
