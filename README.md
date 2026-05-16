# DevAssist Chatbot
A programming-only AI assistant with document-based RAG support.

---

## What It Does
- Answers **programming questions only** (declines weather, cooking, etc.)
- Streams responses in real-time
- Upload a PDF/TXT/MD file → ask questions about it (RAG)
- Code blocks with syntax highlighting

---

## Tech Stack
| Layer | Technology |
|---|---|
| Frontend | Vue 3 + TailwindCSS |
| Backend | Python FastAPI |
| AI Model | Groq API (`llama-3.3-70b-versatile`) |
| Vector Store | FAISS (in-memory) |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 (runs locally) |
| Communication | WebSocket (real-time streaming) |

---

## Project Structure
```
Devchatbot/
├── backend/
│   ├── main.py            ← API routes, WebSocket, Groq streaming
│   ├── rag.py             ← FAISS vector store, chunking, embeddings
│   ├── requirements.txt   ← Python packages
│   └── .env               ← Your Groq API key (never share this)
│
└── frontend/
    ├── src/
    │   ├── App.vue        ← Full UI (sidebar + chat)
    │   ├── main.js        ← Vue entry point
    │   └── style.css      ← Tailwind styles
    ├── index.html
    ├── package.json
    └── vite.config.js
```

---

## Setup Guide

### Step 1 — Get a Free Groq API Key
1. Go to [https://console.groq.com](https://console.groq.com) and sign up
2. Click **API Keys** → **Create API Key**
3. Copy the key (looks like `gsk_...`)

---

### Step 2 — Backend Setup
Open terminal inside the `backend/` folder:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create a file named `.env` inside `backend/` and add:
```
GROQ_API_KEY=paste_your_key_here
```

---

### Step 3 — Frontend Build
Open terminal inside the `frontend/` folder:

```bash
npm install
npm run build
```

---

### Step 4 — Run the App
Go back to the `backend/` folder and run:

```bash
venv\Scripts\activate
uvicorn main:app --reload --port 8001
```

Open your browser → [http://localhost:8001](http://localhost:8001)

You should see the DevAssist UI with 🟢 Connected status.

---

### Step 5 — Share Publicly via ngrok
Install ngrok once:
```bash
winget install ngrok.ngrok
```

Authenticate once (get token from [https://dashboard.ngrok.com](https://dashboard.ngrok.com)):
```bash
ngrok config add-authtoken YOUR_TOKEN
```

Start tunnel:
```bash
ngrok http 8001
```

Share the URL ngrok gives you — it works for anyone in the world.

---

## How to Use

**Ask a programming question** → type in the chat box and press Enter

**Upload a document** → click the upload area in the left sidebar → upload `.pdf`, `.txt`, or `.md` (max 5MB) → ask questions about it

**Topic restriction** → asking about weather, food, or anything non-programming will be politely declined

---

## Notes
- Chat history is session-only — refreshing the page clears it
- Uploaded documents are stored in memory — restarting the server clears them
- If you get a rate limit error, wait 10 seconds and try again (Groq free tier limit)
- First response may take 2–3 seconds (model warmup)