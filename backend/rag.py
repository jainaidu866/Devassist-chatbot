"""
rag.py — DevAssist RAG Module (TurboVec Edition)
Replaces FAISS with TurboVec IdMapIndex.
Public API is IDENTICAL to the old rag.py — main.py needs zero changes.

What changed vs old rag.py:
  - `import faiss` removed
  - `faiss.IndexFlatL2` replaced with `turbovec.IdMapIndex`
  - Internal _index operations updated to TurboVec API
  - Everything else (chunking, embedding, retrieve_context, get_store_info, clear_store) is identical

SRS Compliance:
  - 384-dim embeddings (all-MiniLM-L6-v2)       ✓
  - 500 char chunks, 50 char overlap              ✓
  - Top-3 retrieval                               ✓
  - In-memory transient storage (lost on restart) ✓
  - Filename-filtered search (TurboVec allowlist) ✓ NEW BONUS FEATURE
"""

import io
import numpy as np
import fitz  # PyMuPDF

from sentence_transformers import SentenceTransformer
from turbovec import IdMapIndex
from typing import Optional

# ── Model (loaded once at startup, fully local — no embedding API costs) ─────
EMBED_MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
EMBED_DIM   = 384   # all-MiniLM-L6-v2 output dimension
BIT_WIDTH   = 4     # 4-bit quantization → ~8x compression vs float32

# ── In-memory store ────────────────────────────────────────────────────────────
# _index      : TurboVec IdMapIndex (None until first document added)
# _chunks     : list[str]  — parallel to _ids; chunk text at position i
# _doc_names  : list[str]  — which file each chunk came from
# _ids        : list[int]  — uint64 IDs stored in the index (== position in _chunks)
# _needs_rebuild : True when new embeddings have been staged but index not rebuilt yet

_index:         Optional[IdMapIndex] = None
_chunks:        list[str]            = []
_doc_names:     list[str]            = []
_ids:           list[int]            = []

# Staging buffers — collected then added in one batch for efficiency
_pending_embeddings: list[np.ndarray] = []
_pending_ids:        list[int]        = []
_needs_rebuild:      bool             = False


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


# ─────────────────────────── CHUNKING ────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """
    Split text into overlapping chunks.
    SRS 3.3: chunk_size=500 chars, overlap=50 chars.
    """
    chunks = []
    start  = 0
    length = len(text)

    while start < length:
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap

    return [c.strip() for c in chunks if c.strip()]


# ─────────────────────────── REBUILD HELPER ──────────────────────────────────

def _rebuild_index() -> None:
    """
    Flush staged embeddings into the TurboVec index.
    Called lazily before the first search after any add.
    """
    global _index, _pending_embeddings, _pending_ids, _needs_rebuild

    if not _pending_embeddings:
        _needs_rebuild = False
        return

    all_embeddings = np.vstack(_pending_embeddings).astype(np.float32)
    all_ids        = np.array(_pending_ids, dtype=np.uint64)

    if _index is None:
        # First-ever build
        _index = IdMapIndex(dim=EMBED_DIM, bit_width=BIT_WIDTH)

    _index.add_with_ids(all_embeddings, all_ids)

    _pending_embeddings.clear()
    _pending_ids.clear()
    _needs_rebuild = False


# ─────────────────────────── EMBEDDING & INDEXING ────────────────────────────

def add_document(file_bytes: bytes, filename: str) -> int:
    """
    Full ingestion pipeline:
      extract text → chunk → embed (local) → stage in TurboVec
    Returns number of chunks processed.

    Public API identical to old rag.py.
    """
    global _index, _chunks, _doc_names, _ids, _needs_rebuild

    text   = extract_text(file_bytes, filename)
    chunks = chunk_text(text)

    if not chunks:
        return 0

    # Embed all chunks locally — normalize=True improves cosine similarity recall
    embeddings = EMBED_MODEL.encode(
        chunks,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    embeddings = np.array(embeddings, dtype=np.float32)

    # Assign uint64 IDs continuing from current store size
    start_id = len(_chunks)
    new_ids  = list(range(start_id, start_id + len(chunks)))

    # Update parallel lists
    _chunks.extend(chunks)
    _doc_names.extend([filename] * len(chunks))
    _ids.extend(new_ids)

    # Stage embeddings for lazy rebuild
    _pending_embeddings.append(embeddings)
    _pending_ids.extend(new_ids)
    _needs_rebuild = True

    return len(chunks)


# ─────────────────────────── RETRIEVAL ───────────────────────────────────────

def retrieve_context(query: str, top_k: int = 3, filename_filter: Optional[str] = None) -> str:
    """
    Embed query → search TurboVec → return top-k chunks as context string.
    SRS 3.3: top 3 matching chunks appended to system prompt.

    Args:
        query           : user's question
        top_k           : number of chunks to retrieve (default 3 per SRS)
        filename_filter : if set, restrict results to chunks from this file only
                          (uses TurboVec's built-in allowlist — in-kernel, fast)

    Returns empty string if no documents uploaded.
    Public API is a superset of old rag.py (filename_filter is new optional param).
    """
    global _needs_rebuild

    if not _chunks:
        return ""

    # Rebuild index if new docs were staged since last search
    if _needs_rebuild:
        _rebuild_index()

    if _index is None:
        return ""

    # Embed query
    query_vec = EMBED_MODEL.encode(
        [query],
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    query_vec = np.array(query_vec, dtype=np.float32)  # shape: (1, 384)

    # Build allowlist for filename filtering (TurboVec in-kernel filtering)
    allowlist = None
    if filename_filter:
        allowed_ids = [
            i for i, name in enumerate(_doc_names)
            if name == filename_filter
        ]
        if not allowed_ids:
            return ""
        allowlist = np.array(allowed_ids, dtype=np.uint64)

    # Search
    if allowlist is not None:
        scores, ids = _index.search(query_vec, k=top_k, allowlist=allowlist)
    else:
        scores, ids = _index.search(query_vec, k=top_k)

    # Collect results
    retrieved = []
    for chunk_id in ids[0]:
        idx = int(chunk_id)
        if 0 <= idx < len(_chunks):
            retrieved.append(_chunks[idx])

    if not retrieved:
        return ""

    context_parts = [
        f"[Document Chunk {i + 1}]:\n{chunk}"
        for i, chunk in enumerate(retrieved)
    ]
    return "\n\n".join(context_parts)


# ─────────────────────────── STORE STATUS ────────────────────────────────────

def get_store_info() -> dict:
    """Return info about what's currently stored. Identical API to old rag.py."""
    return {
        "total_chunks":   len(_chunks),
        "documents":      list(set(_doc_names)),
        "has_documents":  len(_chunks) > 0,
    }


def clear_store() -> None:
    """Clear all uploaded documents from memory. Identical API to old rag.py."""
    global _index, _chunks, _doc_names, _ids, _pending_embeddings, _pending_ids, _needs_rebuild

    _index              = None
    _chunks             = []
    _doc_names          = []
    _ids                = []
    _pending_embeddings = []
    _pending_ids        = []
    _needs_rebuild      = False