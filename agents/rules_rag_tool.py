"""
RAG tool answering questions about F1 sporting/technical regulations.
"""

from __future__ import annotations
from pathlib import Path
import asyncio
import re
from functools import lru_cache
from threading import Lock

from agents.llm import get_llm
from agents.errors import handle_tool_errors, tool_error

CHROMA_DIR = Path(__file__).parent.parent / "data" / "chroma"
COLLECTION_NAME = "fia_regulations"
REGULATION_YEAR = 2026
_collection_lock = Lock()


@lru_cache(maxsize=1)
def _load_collection(directory: Path):
    """Open an existing store and load embeddings only when RAG is used.

    Failed initialization is not cached, so building the store and retrying
    works without restarting the agent.
    """
    if not (directory / "chroma.sqlite3").is_file():
        raise FileNotFoundError("The regulation vector store has not been built.")

    import chromadb
    from chromadb.utils import embedding_functions

    client = chromadb.PersistentClient(path=str(directory))
    if COLLECTION_NAME not in {collection.name for collection in client.list_collections()}:
        raise FileNotFoundError("The fia_regulations collection is missing.")
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    return client.get_collection(COLLECTION_NAME, embedding_function=embed_fn)


def get_regulation_collection():
    # lru_cache alone can initialize twice on concurrent first calls.
    with _collection_lock:
        return _load_collection(CHROMA_DIR)

RAG_PROMPT = """You are answering questions about official F1 regulations using ONLY the excerpts below.
All excerpts are from the {regulation_year} FIA regulation corpus. Begin your
answer with "Under the {regulation_year} regulations" so the scope is explicit.
These documents do not establish what rules applied in another season or
whether a historical race-control decision was correct. If the question needs
another year's rules, explain that those documents are unavailable. Do not
infer that rules stayed the same, or claim to have compared different years.
If the excerpts don't contain the answer, say so clearly instead of guessing.

Excerpts:
{context}

Question: {question}

Answer, and cite the source document + page for each claim."""


def retrieve_regulation_chunks(query: str, n_results: int = 5) -> list[dict]:
    results = get_regulation_collection().query(query_texts=[query], n_results=n_results)
    return [
        {"text": doc, "source": meta["source"], "page": meta["page"], "distance": dist}
        for doc, meta, dist in zip(
            results["documents"][0], results["metadatas"][0], results["distances"][0]
        )
    ]


@handle_tool_errors
async def answer_regulation_question(question: str, year: int = REGULATION_YEAR) -> dict:
    # Also guard explicit years in direct calls where the caller omitted year.
    mentioned_years = {int(value) for value in re.findall(r"\b(?:19|20)\d{2}\b", question)}
    unsupported_years = sorted(({year} | mentioned_years) - {REGULATION_YEAR})
    if unsupported_years:
        return {
            **tool_error(
                "unsupported_regulation_year",
                f"Only {REGULATION_YEAR} regulation documents are available; "
                f"rules for {', '.join(map(str, unsupported_years))} cannot be verified.",
                "Provide the regulation documents for the requested year, or ask specifically about 2026 rules.",
            ),
            "regulation_year": REGULATION_YEAR,
            "unavailable_years": unsupported_years,
            "sources": [],
        }
    try:
        chunks = await asyncio.to_thread(retrieve_regulation_chunks, question)
    except FileNotFoundError as error:
        return tool_error("missing_regulations", str(error),
                          "Run uv run python -m ingestion.build_vector_store, then retry.")
    if not chunks:
        return tool_error("no_data", "No regulation excerpts were retrieved.",
                          "Check that the regulation collection has been populated.")
    context = "\n\n".join(f"[{c['source']} p.{c['page']}]\n{c['text']}" for c in chunks)
    prompt = RAG_PROMPT.format(context=context, question=question, regulation_year=REGULATION_YEAR)

    # Use the shared synchronous client in a worker: it is reusable across
    # Streamlit's separate asyncio.run() calls without retaining an old loop.
    response = await asyncio.to_thread(get_llm().invoke, prompt)
    return {
        "answer": response.content,
        "regulation_year": REGULATION_YEAR,
        "sources": [{"source": c["source"], "page": c["page"]} for c in chunks],
    }
