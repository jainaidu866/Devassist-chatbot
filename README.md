# ⚡ DevAssist Chatbot

DevAssist is a programming-focused AI chatbot built for developers. It answers software engineering questions in real time and lets you upload documents (PDF, TXT, MD) to ask questions directly from their content. When a document is uploaded, it automatically generates an AI summary and smart suggested questions tailored to that document. All responses stream token by token via WebSocket. It strictly stays on topic — general questions like weather or cooking are declined by design, keeping the assistant focused and reliable for development work.

---

## 🎥 Demo Video

[![DevAssist Demo](https://img.shields.io/badge/Watch%20Demo-YouTube-red?style=for-the-badge&logo=youtube)](https://youtu.be/GlJPwaLY5Qs?feature=shared)

> See DevAssist in action — document upload, auto Q&A generation, real-time streaming responses, and RAG-powered answers.

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
- Upload a PDF, TXT, or MD file (max 5MB) → get an AI summary + smart suggested questions automatically
- Click any suggested question — answers stream in real time
- Answers use your document as context (RAG)
- Responses stream token by token via WebSocket
- Off-topic questions are declined by design

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