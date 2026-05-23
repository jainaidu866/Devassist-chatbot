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

# ── System prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = (
    "You are a helpful coding assistant. "
    "You strictly answer questions related to software engineering, algorithms, "
    "system design, and code. "
    "If a user asks about general topics (weather, news, cooking, casual chat), "
    "politely decline and state that you are designed only for programming assistance. "
    "When answering, use markdown formatting with proper code blocks and syntax highlighting."
)

# ── Document analysis prompt — generates real summary + 10 balanced questions ─
DOC_ANALYSIS_PROMPT = """You are an expert document analyst. Read the provided document text carefully and return ONLY a valid JSON object in this exact format, nothing else — no markdown, no explanation, no code fences:

{
  "summary": "A detailed 4-6 sentence summary covering: what the document is, its purpose, key topics, and important details specific to this document.",
  "suggested_questions": [
    "Question 1",
    "Question 2",
    "Question 3",
    "Question 4",
    "Question 5",
    "Question 6",
    "Question 7",
    "Question 8",
    "Question 9",
    "Question 10"
  ]
}

Rules:
- Summary must be informative and specific to this document's actual content — not generic.
- Generate EXACTLY 10 suggested questions.
- Questions must be easy to understand but specific to this document — not too simple (avoid "What is this document?") and not too complex.
- Good question difficulty level: a first-time reader of this document should be able to understand the question immediately and be curious to know the answer.
- Questions should be short (under 15 words), clear, and directly answerable from the document.
- Cover different sections and topics of the document across the 10 questions.
- Do NOT ask questions that require cross-referencing multiple sections or deep legal/technical analysis.
- Do NOT use generic questions like "What is this document about?" or "Summarize the key points".
- Return ONLY the raw JSON object. No preamble, no markdown fences, no explanation."""

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


# ── Helper: generate real AI summary + 10 smart questions from document ───────
async def generate_doc_summary_and_questions(filename: str) -> dict:
    """
    Samples chunks from beginning, middle, and end of the uploaded document,
    sends them to Groq, and returns a real AI-generated summary + 10 smart questions.
    Falls back to generic values if Groq fails.
    """
    all_chunks = rag._chunks
    total = len(all_chunks)

    if not all_chunks:
        return {
            "summary": f"**{filename}** has been processed. You can now ask questions about it.",
            "suggested_questions": [
                "What is the main purpose of this document?",
                "What are the key rules or guidelines described?",
                "What procedures or processes are outlined?",
                "What rights or duties are mentioned?",
                "Who is the intended audience of this document?",
                "What are the eligibility criteria mentioned?",
                "What are the important deadlines or timelines?",
                "What terms and conditions are described?",
                "What are the consequences of non-compliance?",
                "What resources or references are provided?",
            ]
        }

    # Sample from beginning (most important for context), middle, and end
    indices = set()
    # First 3 chunks — intro/overview
    for i in range(min(3, total)):
        indices.add(i)
    # Middle 3 chunks
    mid = total // 2
    for i in range(mid, min(mid + 3, total)):
        indices.add(i)
    # Last 2 chunks
    for i in range(max(0, total - 2), total):
        indices.add(i)

    sampled = [all_chunks[i] for i in sorted(indices)]

    # Combine, capped at 4000 chars so we stay within token limits
    combined_text = "\n\n---\n\n".join(sampled)
    combined_text = combined_text[:4000]

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": DOC_ANALYSIS_PROMPT},
                {"role": "user", "content": f"Document filename: {filename}\n\nDocument content:\n\n{combined_text}"},
            ],
            max_tokens=1200,
            temperature=0.3,
        )

        raw = response.choices[0].message.content.strip()

        # Strip markdown fences if model wrapped anyway
        if "```" in raw:
            parts = raw.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    raw = part
                    break
        raw = raw.strip()

        result = json.loads(raw)

        summary = result.get("summary", "").strip()
        questions = result.get("suggested_questions", [])

        if not summary or len(summary) < 50:
            raise ValueError("Summary too short")
        if not questions or len(questions) < 2:
            raise ValueError("Not enough questions generated")

        return {
            "summary": summary,
            "suggested_questions": questions[:10],
        }

    except Exception as e:
        print(f"⚠️  Doc analysis failed: {e}. Using fallback.")
        return {
            "summary": f"**{filename}** has been processed and indexed ({total} chunks). You can now ask questions about its content.",
            "suggested_questions": [
                "What is the main purpose of this document?",
                "What are the key rules or guidelines described?",
                "What procedures or processes are outlined?",
                "What rights or duties are mentioned?",
                "Who is the intended audience of this document?",
                "What are the eligibility criteria mentioned?",
                "What are the important deadlines or timelines?",
                "What terms and conditions are described?",
                "What are the consequences of non-compliance?",
                "What resources or references are provided?",
            ]
        }


# ────────────────────────────────────────────────────────────────────────────
# POST /upload
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

    # Generate real AI summary + 10 smart suggested questions after indexing
    doc_analysis = await generate_doc_summary_and_questions(filename)

    return {
        "status": "ok",
        "chunks": chunks_processed,
        "filename": filename,
        "summary": doc_analysis["summary"],
        "suggested_questions": doc_analysis["suggested_questions"],
    }


# ────────────────────────────────────────────────────────────────────────────
# POST /generate-qa
# ────────────────────────────────────────────────────────────────────────────
@app.post("/generate-qa")
async def generate_qa():
    store = rag.get_store_info()
    if not store["has_documents"]:
        raise HTTPException(
            status_code=400,
            detail="No documents uploaded. Please upload a PDF/TXT/MD file first."
        )

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

    all_chunks = rag._chunks
    total = len(all_chunks)
    step = max(1, total // 10)
    sampled_chunks = [all_chunks[i] for i in range(0, total, step)][:10]

    all_qa_pairs = []

    for i, chunk in enumerate(sampled_chunks):
        if len(chunk.strip()) < 100:
            continue

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

            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            qa_list = json.loads(raw)

            for item in qa_list:
                if "question" in item and "answer" in item:
                    all_qa_pairs.append({
                        "question": item["question"],
                        "answer": item["answer"],
                        "chunk_index": i + 1,
                    })

        except json.JSONDecodeError:
            continue
        except RateLimitError:
            break
        except Exception:
            continue

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


# ── POST /clear-document ──────────────────────────────────────────────────────
@app.post("/clear-document")
async def clear_document():
    rag.clear_store()
    return {"status": "cleared"}


# ────────────────────────────────────────────────────────────────────────────
# WebSocket /ws
# Incoming: { "type": "message", "content": "..." }
# Outgoing: { "type": "start" | "token" | "end" | "error", "content": "..." }
# ────────────────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    print("🔌 WebSocket connection established.")

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
                if payload.get("type") == "message":
                    user_message = payload.get("content", "").strip()
                else:
                    user_message = payload.get("message", "").strip()
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "content": "Invalid JSON payload.",
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
                await websocket.send_text(json.dumps({"type": "start"}))

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
                            "type": "token",
                            "content": delta.content,
                        }))
                        await asyncio.sleep(0)

                await websocket.send_text(json.dumps({"type": "end"}))

            except RateLimitError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "content": "Traffic is high. Please wait 10 seconds before asking again.",
                }))

            except Exception as e:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "content": f"An unexpected error occurred: {str(e)}",
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
        if full_path.startswith(("upload", "store-info", "clear-store", "generate-qa", "clear-document", "ws", "docs", "openapi")):
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))