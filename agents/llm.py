import os
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

@lru_cache(maxsize=4)
def get_llm(temperature: float = 0):
    """Build a shared model on first use; restart to apply config changes."""
    from langchain_openrouter import ChatOpenRouter

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("Set OPENROUTER_API_KEY before asking the agent a question.")
    return ChatOpenRouter(
        model=os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
        api_key=api_key,
        temperature=temperature,
    )
