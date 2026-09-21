import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path

CHROMA_DIR = Path("data/chroma")
embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
client = chromadb.PersistentClient(path=str(CHROMA_DIR))
collection = client.get_collection("fia_regulations", embedding_function=embed_fn)

results = collection.query(query_texts=["how many mandatory pit stops are required in a dry race"], n_results=3)
for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
    print(f"[page {meta['page']}] {doc[:200]}...\n")