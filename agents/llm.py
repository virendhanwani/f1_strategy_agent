import os
from dotenv import load_dotenv
from langchain_openrouter import ChatOpenRouter

load_dotenv()

OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")


def get_llm(temperature: float = 0):
    return ChatOpenRouter(
        model=OPENROUTER_MODEL,
        api_key=os.environ["OPENROUTER_API_KEY"],
        temperature=temperature,
    )