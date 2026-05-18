# ⚡ DevAssist Chatbot

A programming-only AI assistant with real-time streaming and document Q&A (RAG).

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Vue 3 + TailwindCSS |
| Backend | Python FastAPI |
| AI Model | Groq API (`llama-3.3-70b-versatile`) |
| Vector Store | FAISS (in-memory) |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 |
| Communication | WebSocket |

---

## Setup

**1. Get a Groq API key** at [console.groq.com](https://console.groq.com) → API Keys → Create

**2. Backend**
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```
Create `backend/.env`:
```
GROQ_API_KEY=your_key_here
```

**3. Frontend**
```bash
cd frontend
npm install
npm run build
```

**4. Run**
```bash
cd backend
uvicorn main:app --reload --port 8001
```
Open → [http://localhost:8001](http://localhost:8001)

---

## Features

- Ask any programming / software engineering question
- Upload a PDF, TXT, or MD file (max 5MB) → get an AI summary + smart suggested questions
- Click any suggested question — suggestions stay visible, chat never clears
- Answers use your document as context (RAG)
- Responses stream in real time token by token

---

## Share Publicly via ngrok

```bash
ngrok http 8001
```
Share the URL ngrok gives you — works for anyone worldwide.

---

## Common Issues

| Problem | Fix |
|---|---|
| 🔴 WebSocket 403 | Backend not running, or wrong port |
| GROQ_API_KEY error | `.env` must be inside `backend/` folder |
| Rate limit error | Wait 10 seconds (Groq free tier limit) |
| UI not updating | Run `npm run build` then restart backend |

---

## Notes

- Chat history and uploaded documents are **session only** — cleared on server restart
- Only **one document** active at a time
- Off-topic questions (weather, cooking, etc.) are declined by design