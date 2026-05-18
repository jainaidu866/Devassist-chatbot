"""
main.py — DevAssist Chatbot Backend
FastAPI + WebSocket + Groq streaming + RAG + Q&A Generation + Serves Vue Frontend
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

# ── Load environment variables ───────────────────────────────────────────────
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY not found in .env file!")

groq_client = Groq(api_key=GROQ_API_KEY)

# ── System prompt (SRS 3.2) ──────────────────────────────────────────────────
SYSTEM_PROMPT = (
    "You are a helpful coding assistant. "
    "You strictly answer questions related to software engineering, algorithms, "
    "system design, and code. "
    "If a user asks about general topics (weather, news, cooking, casual chat), "
    "politely decline and state that you are designed only for programming assistance. "
    "When answering, use markdown formatting with proper code blocks and syntax highlighting."
)

# ── Q&A Generation prompt ────────────────────────────────────────────────────
QA_SYSTEM_PROMPT = """You are a document analysis expert. 
Your job is to read the given text and generate meaningful question and answer pairs from it.
Generate exactly 3 question-answer pairs.
Return ONLY a valid JSON array in this exact format, nothing else:
[
  {"question": "...", "answer": "..."},
  {"question": "...", "answer": "..."},
  {"question": "...", "answer": "..."}
]
Make questions specific and answers detailed based only on the provided text."""

ALLOWED_EXTENSIONS = {"txt", "md", "pdf"}
MAX_FILE_SIZE_MB = 5
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")


# ── App startup ──────────────────────────────────────────────────────────────
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
    description="Programming-only chatbot with RAG + Q&A Generation",
    version="1.0.0",
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
# POST /upload  (SRS 4.1)
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
            detail=f"File too large ({size_mb:.1f}MB). Maximum is {MAX_FILE_SIZE_MB}MB.",
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


# ────────────────────────────────────────────────────────────────────────────
# POST /generate-qa  ← NEW ENDPOINT
# Takes uploaded document chunks and generates Q&A pairs using Groq
# ────────────────────────────────────────────────────────────────────────────
@app.post("/generate-qa")
async def generate_qa():
    """
    Generate Q&A pairs from all uploaded document chunks.
    Process: pick every Nth chunk → send to Groq → collect Q&A pairs → return all.
    This replicates what NotebookLM does, using our own Groq + FAISS pipeline.
    """
    store = rag.get_store_info()
    if not store["has_documents"]:
        raise HTTPException(
            status_code=400,
            detail="No documents uploaded. Please upload a PDF/TXT/MD file first."
        )

    all_chunks = rag._chunks  # access internal chunk list

    # Sample chunks evenly — pick every Nth chunk to cover whole document
    # Max 10 chunks to stay within Groq rate limits
    total = len(all_chunks)
    step = max(1, total // 10)
    sampled_chunks = [all_chunks[i] for i in range(0, total, step)][:10]

    all_qa_pairs = []

    for i, chunk in enumerate(sampled_chunks):
        if len(chunk.strip()) < 100:
            continue  # skip very short chunks

        try:
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": QA_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Generate Q&A pairs from this text:\n\n{chunk}"},
                ],
                max_tokens=600,
                temperature=0.3,
            )

            raw = response.choices[0].message.content.strip()

            # Clean up response — strip markdown code fences if present
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            qa_list = json.loads(raw)

            # Validate structure
            for item in qa_list:
                if "question" in item and "answer" in item:
                    all_qa_pairs.append({
                        "question": item["question"],
                        "answer": item["answer"],
                        "chunk_index": i + 1,
                    })

        except json.JSONDecodeError:
            # Skip chunks where Groq didn't return valid JSON
            continue
        except RateLimitError:
            # If rate limited, return what we have so far
            break
        except Exception:
            continue

        # Small delay between requests to respect Groq rate limits
        await asyncio.sleep(1)

    if not all_qa_pairs:
        raise HTTPException(
            status_code=500,
            detail="Could not generate Q&A pairs. Try again in a few seconds."
        )

    return {
        "status": "success",
        "total_qa_pairs": len(all_qa_pairs),
        "document": store["documents"],
        "qa_pairs": all_qa_pairs,
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
# WebSocket /ws/chat  (SRS 4.2)
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
        if full_path.startswith(("upload", "store-info", "clear-store", "generate-qa", "ws", "docs", "openapi")):
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))