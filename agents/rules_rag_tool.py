"""
RAG tool answering questions about F1 sporting/technical regulations.
"""

from __future__ import annotations
from pathlib import Path
import os

import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from langchain_openrouter import ChatOpenRouter
from agents.llm import get_llm

load_dotenv()

CHROMA_DIR = Path(__file__).parent.parent / "data" / "chroma"
COLLECTION_NAME = "fia_regulations"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL")

_embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
_collection = _client.get_collection(COLLECTION_NAME, embedding_function=_embed_fn)
_llm = get_llm()

RAG_PROMPT = """You are answering questions about official F1 regulations using ONLY the excerpts below.
If the excerpts don't contain the answer, say so clearly instead of guessing.

Excerpts:
{context}

Question: {question}

Answer, and cite the source document + page for each claim."""


def retrieve_regulation_chunks(query: str, n_results: int = 5) -> list[dict]:
    results = _collection.query(query_texts=[query], n_results=n_results)
    return [
        {"text": doc, "source": meta["source"], "page": meta["page"], "distance": dist}
        for doc, meta, dist in zip(
            results["documents"][0], results["metadatas"][0], results["distances"][0]
        )
    ]


async def answer_regulation_question(question: str) -> dict:
    chunks = retrieve_regulation_chunks(question)
    context = "\n\n".join(f"[{c['source']} p.{c['page']}]\n{c['text']}" for c in chunks)
    prompt = RAG_PROMPT.format(context=context, question=question)

    response = await _llm.ainvoke(prompt)
    return {
        "answer": response.content,
        "sources": [{"source": c["source"], "page": c["page"]} for c in chunks],
    }
