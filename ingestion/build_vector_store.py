from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
import re
import chromadb
from chromadb.utils import embedding_functions
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter

REGULATIONS_DIR = Path(__file__).parent.parent / "data" / "regulations"
CHROMA_DIR = Path(__file__).parent.parent / "data" / "chroma"
COLLECTION_NAME = "fia_regulations"


CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
TOC_LINE_PATTERN = re.compile(r"\.{3,}\s*\d+\s*$")

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],   # tried in order — paragraph first, char-level last resort
)

@dataclass
class Chunk:
    text: str
    page: int
    chunk_index: int
    source: str

def is_toc_page(text: str, threshold: float = 0.25) -> bool:
    """
    Flags a page as table-of-contents if a large fraction of its lines match
    the dot-leader-then-page-number pattern typical of a TOC entry. Content
    pages occasionally have a stray matching line, but not >25% of them.
    """
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return False
    toc_like = sum(1 for l in lines if TOC_LINE_PATTERN.search(l))
    return (toc_like / len(lines)) >= threshold

def extract_pages(pdf_path: Path) -> list[tuple[int, str]]:
    reader = PdfReader(str(pdf_path))
    pages = []
    skipped_toc = 0
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if not text.strip():
            continue
        if is_toc_page(text):
            skipped_toc += 1
            continue
        pages.append((i + 1, text))
    if skipped_toc:
        print(f"    skipped {skipped_toc} TOC page(s) in {pdf_path.name}")
    return pages

def chunk_text(text: str, page: int, start_index: int, source: str) -> list[Chunk]:
    pieces = _splitter.split_text(text)
    return [
        Chunk(text=piece.strip(), page=page, chunk_index=start_index + i, source=source)
        for i, piece in enumerate(pieces)
        if piece.strip()
    ]

def build_chunks(pdf_dir: Path) -> list[Chunk]:
    all_chunks: list[Chunk] = []
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in {pdf_dir}")

    for pdf_path in pdf_files:
        print(f"  Processing {pdf_path.name}...")
        pages = extract_pages(pdf_path)
        for page_num, text in pages:
            all_chunks.extend(
                chunk_text(text, page_num, start_index=len(all_chunks), source=pdf_path.name)
            )
    return all_chunks

def main() -> None:
    if not REGULATIONS_DIR.exists():
        raise FileNotFoundError(
            f"Place the FIA Sporting Regulations PDFs in {REGULATIONS_DIR} before running this."
        )

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    print("Extracting and chunking PDF...")
    chunks = build_chunks(REGULATIONS_DIR)
    print(f"  -> {len(chunks)} chunks")

    print("Loading local embedding model (all-MiniLM-L6-v2)...")
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    # recreate cleanly each run, so re-running after a regulations update doesn't duplicate chunks
    client.delete_collection(COLLECTION_NAME) if COLLECTION_NAME in [c.name for c in client.list_collections()] else None
    collection = client.create_collection(name=COLLECTION_NAME, embedding_function=embed_fn)

    print("Embedding and writing to Chroma...")
    collection.add(
        ids=[f"chunk_{c.chunk_index}" for c in chunks],
        documents=[c.text for c in chunks],
        metadatas=[{"page": c.page, "chunk_index": c.chunk_index, "source": c.source} for c in chunks],
    )
    print(f"  -> wrote {collection.count()} chunks to collection '{COLLECTION_NAME}'")


if __name__ == "__main__":
    main()