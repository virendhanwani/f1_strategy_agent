"""Offline checks: unsupported years must never reach retrieval or the LLM."""

import asyncio

from agents.rules_rag_tool import answer_regulation_question, _load_collection
from agents.llm import get_llm
from agents.tools import ask_about_regulations


async def main():
    for question, year in [
        ("What were the safety-car rules?", 2021),
        ("What were the 2021 Abu Dhabi safety-car rules?", 2026),
        ("Compare the 2025 and 2026 pit-stop rules", 2026),
        ("What will the pit-stop rules be?", 2027),
    ]:
        result = await answer_regulation_question(question, year=year)
        assert result["code"] == "unsupported_regulation_year"
        assert result["regulation_year"] == 2026
        assert result["sources"] == []
        print(result["error"])

    result = await ask_about_regulations.ainvoke({"question": "Was that permitted?", "year": 2021})
    assert result["unavailable_years"] == [2021]
    assert _load_collection.cache_info().currsize == 0
    assert get_llm.cache_info().currsize == 0
    print("Passed: historical, comparative, future, and follow-up questions report unavailable years without loading resources.")


if __name__ == "__main__":
    asyncio.run(main())
