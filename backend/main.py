"""
main.py — DevAssist Chatbot Backend
FastAPI + WebSocket + Groq streaming + RAG + Serves Vue Frontend
Matches SRS v1.0 exactly (sections 3, 4, 5)
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

# ── Load environment variables from .env ────────────────────────────────────
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY not found in .env file!")

groq_client = Groq(api_key=GROQ_API_KEY)

# ── SRS 3.2: Required system prompt — strict programming-only policy ─────────
SYSTEM_PROMPT = (
    "You are a helpful coding assistant. "
    "You strictly answer questions related to software engineering, algorithms, "
    "system design, and code. "
    "If a user asks about general topics (weather, news, cooking, casual chat), "
    "politely decline and state that you are designed only for programming assistance. "
    "When answering, use markdown formatting with proper code blocks and syntax highlighting."
)

# ── Allowed file extensions (SRS 3.3) ────────────────────────────────────────
ALLOWED_EXTENSIONS = {"txt", "md", "pdf"}
MAX_FILE_SIZE_MB = 5

# ── Path to Vue built files ──────────────────────────────────────────────────
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")


# ── App startup: pre-load embedding model ───────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🔧 Loading sentence-transformer model...")
    _ = rag.EMBED_MODEL.encode(["warmup"], show_progress_bar=False)
    print("✅ Model ready. DevAssist backend is live.")
    yield
    print("🛑 Shutting down.")


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="DevAssist Chatbot API",
    description="Programming-only chatbot with RAG (SRS v1.0)",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── ngrok header middleware (skips browser warning for recruiter) ─────────────
@app.middleware("http")
async def add_ngrok_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response


# ────────────────────────────────────────────────────────────────────────────
# SRS 4.1 — POST /upload
# ────────────────────────────────────────────────────────────────────────────
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{ext}'. Allowed: {ALLOWED_EXTENSIONS}",
        )

    file_bytes = await file.read()
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size_mb:.1f}MB). Maximum allowed is {MAX_FILE_SIZE_MB}MB.",
        )

    try:
        chunks_processed = rag.add_document(file_bytes, filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")

    return {
        "status": "success",
        "chunks_processed": chunks_processed,
        "filename": filename,
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
# SRS 4.2 — WebSocket /ws/chat
# ────────────────────────────────────────────────────────────────────────────
@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    print("🔌 WebSocket connection established.")

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
                user_message = payload.get("message", "").strip()
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "status": "error",
                    "message": "Invalid JSON payload.",
                }))
                continue

            if not user_message:
                continue

            context = rag.retrieve_context(user_message, top_k=3)

            if context:
                truncated_context = context[:3000]
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
                            "token": delta.content,
                            "status": "streaming",
                        }))
                        await asyncio.sleep(0)

                await websocket.send_text(json.dumps({"status": "done"}))

            except RateLimitError:
                await websocket.send_text(json.dumps({
                    "status": "error",
                    "message": "Traffic is high. Please wait 10 seconds before asking again.",
                }))

            except Exception as e:
                await websocket.send_text(json.dumps({
                    "status": "error",
                    "message": f"An unexpected error occurred: {str(e)}",
                }))

    except WebSocketDisconnect:
        print("🔌 WebSocket disconnected.")


# ────────────────────────────────────────────────────────────────────────────
# Serve Vue Frontend — MUST BE AT THE BOTTOM after all API routes
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
        if full_path.startswith(("upload", "store-info", "clear-store", "ws", "docs", "openapi")):
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))