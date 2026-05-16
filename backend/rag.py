"""
rag.py — Retrieval-Augmented Generation module
Handles: text chunking, local embedding (sentence-transformers), FAISS vector store
Per SRS Section 3.3: chunk=500 chars, overlap=50, top-3 retrieval, in-memory only
"""

import io
import fitz  # PyMuPDF for PDF parsing
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

# ── Model (loaded once at startup, runs fully locally — no embedding costs) ──
EMBED_MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
EMBED_DIM = 384  # all-MiniLM-L6-v2 output dimension

# ── In-memory store (SRS 5.2: lost on server restart — acceptable for MVP) ──
_index: faiss.IndexFlatL2 | None = None
_chunks: list[str] = []          # parallel list: chunk text at position i matches vector i
_doc_names: list[str] = []       # tracks which file each chunk came from


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
      extract text → chunk → embed → store in FAISS
    Returns number of chunks processed.
    """
    global _index, _chunks, _doc_names

    text = extract_text(file_bytes, filename)
    chunks = chunk_text(text)

    if not chunks:
        return 0

    # Embed all chunks locally
    embeddings = EMBED_MODEL.encode(chunks, show_progress_bar=False)
    embeddings = np.array(embeddings, dtype="float32")

    # Create or update FAISS index
    if _index is None:
        _index = faiss.IndexFlatL2(EMBED_DIM)

    _index.add(embeddings)
    _chunks.extend(chunks)
    _doc_names.extend([filename] * len(chunks))

    return len(chunks)


# ─────────────────────────── RETRIEVAL ──────────────────────────────────────

def retrieve_context(query: str, top_k: int = 3) -> str:
    """
    Embed query → search FAISS → return top-k chunks joined as context string.
    SRS 3.3: top 3 matching chunks appended to system prompt.
    Returns empty string if no documents have been uploaded.
    """
    if _index is None or not _chunks:
        return ""

    query_vec = EMBED_MODEL.encode([query], show_progress_bar=False)
    query_vec = np.array(query_vec, dtype="float32")

    distances, indices = _index.search(query_vec, top_k)

    retrieved = []
    for idx in indices[0]:
        if 0 <= idx < len(_chunks):
            retrieved.append(_chunks[idx])

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
        "has_documents": _index is not None and len(_chunks) > 0,
    }


def clear_store():
    """Clear all uploaded documents from memory."""
    global _index, _chunks, _doc_names
    _index = None
    _chunks = []
    _doc_names = []