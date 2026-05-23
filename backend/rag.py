"""
rag.py — Retrieval-Augmented Generation module
Handles: text chunking, local embedding (sentence-transformers), ChromaDB vector store
Per SRS Section 3.3: chunk=500 chars, overlap=50, top-3 retrieval
"""

import io
import uuid
import fitz  # PyMuPDF for PDF parsing
from sentence_transformers import SentenceTransformer
import chromadb

# ── Model (loaded once at startup, runs fully locally — no embedding costs) ──
EMBED_MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

# ── ChromaDB in-memory client ────────────────────────────────────────────────
_chroma_client = chromadb.Client()
_collection = _chroma_client.get_or_create_collection(name="devassist_docs")

_chunks: list[str] = []       # parallel list: chunk text (used by main.py for doc analysis)
_doc_names: list[str] = []    # tracks which file each chunk came from


# ─────────────────────────── TEXT EXTRACTION ────────────────────────────────

def extract_text(file_bytes: bytes, filename: str) -> str:
    """Extract raw text from .pdf, .txt, or .md files."""
    ext = filename.rsplit(".", 1)[-1].lower()

    if ext == "pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)

    elif ext in ("txt", "md"):
        return file_bytes.decode("utf-8", errors="ignore")

    else:
        raise ValueError(f"Unsupported file type: .{ext}")


# ─────────────────────────── CHUNKING ───────────────────────────────────────

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """
    Split text into overlapping chunks.
    SRS 3.3: chunk_size=500 chars, overlap=50 chars.
    """
    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap  # slide window with overlap

    return [c.strip() for c in chunks if c.strip()]


# ─────────────────────────── EMBEDDING & INDEXING ───────────────────────────

def add_document(file_bytes: bytes, filename: str) -> int:
    """
    Full ingestion pipeline:
      extract text → chunk → embed → store in ChromaDB
    Returns number of chunks processed.
    """
    global _chunks, _doc_names

    text = extract_text(file_bytes, filename)
    chunks = chunk_text(text)

    if not chunks:
        return 0

    # Embed all chunks locally
    embeddings = EMBED_MODEL.encode(chunks, show_progress_bar=False)
    embeddings = [e.tolist() for e in embeddings]

    # Generate unique IDs for each chunk
    ids = [str(uuid.uuid4()) for _ in chunks]

    # Store in ChromaDB with metadata
    _collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=[{"filename": filename} for _ in chunks],
    )

    _chunks.extend(chunks)
    _doc_names.extend([filename] * len(chunks))

    return len(chunks)


# ─────────────────────────── RETRIEVAL ──────────────────────────────────────

def retrieve_context(query: str, top_k: int = 3) -> str:
    """
    Embed query → search ChromaDB → return top-k chunks joined as context string.
    SRS 3.3: top 3 matching chunks appended to system prompt.
    Returns empty string if no documents have been uploaded.
    """
    if not _chunks:
        return ""

    query_vec = EMBED_MODEL.encode([query], show_progress_bar=False)
    query_vec = [query_vec[0].tolist()]

    results = _collection.query(
        query_embeddings=query_vec,
        n_results=min(top_k, len(_chunks)),
    )

    retrieved = results.get("documents", [[]])[0]

    if not retrieved:
        return ""

    # Format as a readable context block
    context_parts = [f"[Document Chunk {i+1}]:\n{chunk}" for i, chunk in enumerate(retrieved)]
    return "\n\n".join(context_parts)


# ─────────────────────────── STORE STATUS ───────────────────────────────────

def get_store_info() -> dict:
    """Return info about what's currently stored in the vector store."""
    return {
        "total_chunks": len(_chunks),
        "documents": list(set(_doc_names)),
        "has_documents": len(_chunks) > 0,
    }


def clear_store():
    """Clear all uploaded documents from ChromaDB and memory."""
    global _chroma_client, _collection, _chunks, _doc_names
    _chroma_client.delete_collection("devassist_docs")
    _collection = _chroma_client.get_or_create_collection(name="devassist_docs")
    _chunks = []
    _doc_names = []