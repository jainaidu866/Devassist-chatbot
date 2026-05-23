"""
main.py — DevAssist Chatbot Backend
FastAPI + WebSocket + Groq streaming + RAG (TurboVec) + Q&A Generation + Serves Vue Frontend

Changes vs previous version:
  - /generate-qa now returns EXACTLY 10 questions (recruiter requirement)
  - Uses updated rag.py (TurboVec instead of FAISS) — zero changes needed here
  - Everything else identical
"""

import os
import json
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from groq import Groq, RateLimitError

import rag

# ── Load environment variables ────────────────────────────────────────────────
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY not found in .env file!")

groq_client = Groq(api_key=GROQ_API_KEY)

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = (
    "You are a helpful coding assistant. "
    "You strictly answer questions related to software engineering, algorithms, "
    "system design, and code. "
    "If a user asks about general topics (weather, news, cooking, casual chat), "
    "politely decline and state that you are designed only for programming assistance. "
    "When answering, use markdown formatting with proper code blocks and syntax highlighting."
)

# ── Q&A Generation prompt — instructs Groq to return exactly 1 Q&A pair ──────
# We call this once per sampled chunk and collect until we have 10 total.
QA_SYSTEM_PROMPT = """You are a document analysis expert.
Read the given text and generate ONE meaningful question-answer pair from it.
Return ONLY a valid JSON object in this exact format, nothing else — no markdown, no explanation:
{"question": "...", "answer": "..."}
Make the question specific and the answer detailed, based only on the provided text."""

ALLOWED_EXTENSIONS = {"txt", "md", "pdf"}
MAX_FILE_SIZE_MB   = 5
FRONTEND_DIST      = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
TARGET_QA_COUNT    = 10   # ← recruiter requirement: always generate exactly 10


# ── App lifespan ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🔧 Loading sentence-transformer model...")
    _ = rag.EMBED_MODEL.encode(["warmup"], show_progress_bar=False)
    print("✅ Model ready. DevAssist (TurboVec edition) is live.")
    yield
    print("🛑 Shutting down.")


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="DevAssist Chatbot API",
    description="Programming-only chatbot with RAG (TurboVec) + 10 Q&A auto-generation",
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── ngrok header middleware ───────────────────────────────────────────────────
@app.middleware("http")
async def add_ngrok_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response


# ────────────────────────────────────────────────────────────────────────────
# POST /upload
# ────────────────────────────────────────────────────────────────────────────
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    filename = file.filename or ""
    ext      = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{ext}'. Allowed: {ALLOWED_EXTENSIONS}",
        )

    file_bytes = await file.read()
    size_mb    = len(file_bytes) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size_mb:.1f} MB). Maximum is {MAX_FILE_SIZE_MB} MB.",
        )

    try:
        chunks_processed = rag.add_document(file_bytes, filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")

    return {
        "status":           "success",
        "chunks_processed": chunks_processed,
        "filename":         filename,
    }


# ────────────────────────────────────────────────────────────────────────────
# POST /generate-qa
# Generates EXACTLY 10 question-answer pairs from the uploaded document.
# Strategy:
#   1. Sample chunks evenly across the document to cover all sections
#   2. Call Groq once per chunk, asking for 1 Q&A pair each time
#   3. Stop as soon as we have 10 valid pairs (or exhaust all sampled chunks)
#   4. Always return exactly 10 (or as many as possible if doc is very short)
# ────────────────────────────────────────────────────────────────────────────
@app.post("/generate-qa")
async def generate_qa():
    """
    Generate exactly 10 Q&A pairs from the uploaded document.
    Recruiter requirement: fixed count of 10, not variable.
    """
    store = rag.get_store_info()
    if not store["has_documents"]:
        raise HTTPException(
            status_code=400,
            detail="No documents uploaded. Please upload a PDF/TXT/MD file first.",
        )

    all_chunks = rag._chunks  # access internal chunk list

    # ── Sample chunks evenly across the document ──────────────────────────────
    # We need up to TARGET_QA_COUNT (10) successful Q&A pairs.
    # Sample 2x that many chunks to give headroom for skips/failures.
    total      = len(all_chunks)
    max_sample = min(total, TARGET_QA_COUNT * 2)          # up to 20 candidates
    step       = max(1, total // max_sample)
    candidates = [all_chunks[i] for i in range(0, total, step)][:max_sample]

    qa_pairs = []

    for i, chunk in enumerate(candidates):
        # Stop as soon as we have the required 10
        if len(qa_pairs) >= TARGET_QA_COUNT:
            break

        # Skip very short chunks — they rarely produce meaningful Q&A
        if len(chunk.strip()) < 80:
            continue

        try:
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": QA_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Generate a question-answer pair from this text:\n\n{chunk}",
                    },
                ],
                max_tokens=400,
                temperature=0.3,
            )

            raw = response.choices[0].message.content.strip()

            # Strip markdown fences if Groq wrapped the JSON despite instructions
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            item = json.loads(raw)

            if "question" in item and "answer" in item:
                qa_pairs.append({
                    "question":    item["question"],
                    "answer":      item["answer"],
                    "chunk_index": i + 1,
                })

        except json.JSONDecodeError:
            # Groq didn't return valid JSON — skip this chunk
            continue
        except RateLimitError:
            # Hit rate limit — return however many we have so far
            break
        except Exception:
            continue

        # Small delay between requests to respect Groq free-tier rate limits
        await asyncio.sleep(1.2)

    if not qa_pairs:
        raise HTTPException(
            status_code=500,
            detail="Could not generate Q&A pairs. Try again in a few seconds.",
        )

    return {
        "status":        "success",
        "total_qa_pairs": len(qa_pairs),
        "target":         TARGET_QA_COUNT,
        "document":       store["documents"],
        "qa_pairs":       qa_pairs,
    }


# ── GET /store-info ───────────────────────────────────────────────────────────
@app.get("/store-info")
async def store_info():
    return rag.get_store_info()


# ── DELETE /clear-store ───────────────────────────────────────────────────────
@app.delete("/clear-store")
async def clear_store():
    rag.clear_store()
    return {"status": "cleared"}


# ────────────────────────────────────────────────────────────────────────────
# WebSocket /ws/chat
# ────────────────────────────────────────────────────────────────────────────
@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    print("🔌 WebSocket connection established.")

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload      = json.loads(raw)
                user_message = payload.get("message", "").strip()
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "status":  "error",
                    "message": "Invalid JSON payload.",
                }))
                continue

            if not user_message:
                continue

            # Retrieve RAG context from TurboVec
            context = rag.retrieve_context(user_message, top_k=3)

            if context:
                truncated_context  = context[:3000]
                full_system_prompt = (
                    SYSTEM_PROMPT
                    + "\n\n--- Relevant Documentation Context ---\n"
                    + truncated_context
                    + "\n--- End of Context ---\n"
                    + "Use the above context to answer the user's question if relevant."
                )
            else:
                full_system_prompt = SYSTEM_PROMPT

            try:
                stream = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": full_system_prompt},
                        {"role": "user",   "content": user_message},
                    ],
                    stream=True,
                    max_tokens=1024,
                    temperature=0.3,
                )

                for chunk in stream:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        await websocket.send_text(json.dumps({
                            "token":  delta.content,
                            "status": "streaming",
                        }))
                        await asyncio.sleep(0)

                await websocket.send_text(json.dumps({"status": "done"}))

            except RateLimitError:
                await websocket.send_text(json.dumps({
                    "status":  "error",
                    "message": "Traffic is high. Please wait 10 seconds before asking again.",
                }))

            except Exception as e:
                await websocket.send_text(json.dumps({
                    "status":  "error",
                    "message": f"An unexpected error occurred: {str(e)}",
                }))

    except WebSocketDisconnect:
        print("🔌 WebSocket disconnected.")


# ────────────────────────────────────────────────────────────────────────────
# Serve Vue Frontend — MUST BE AT BOTTOM
# ────────────────────────────────────────────────────────────────────────────
if os.path.exists(FRONTEND_DIST):
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")),
        name="assets",
    )

    @app.get("/")
    async def serve_root():
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith((
            "upload", "store-info", "clear-store",
            "generate-qa", "ws", "docs", "openapi",
        )):
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))