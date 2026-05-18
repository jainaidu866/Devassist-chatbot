<template>
  <div class="app-shell">

    <!-- ══════════════════ LEFT SIDEBAR ══════════════════ -->
    <aside class="sidebar">

      <!-- Logo -->
      <div class="sidebar-logo">
        <div class="logo-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="16 18 22 12 16 6"></polyline>
            <polyline points="8 6 2 12 8 18"></polyline>
          </svg>
        </div>
        <div>
          <h1 class="logo-title">DevAssist</h1>
          <p class="logo-sub">AI Programming Assistant</p>
        </div>
      </div>

      <!-- Upload Zone -->
      <div class="sidebar-section">
        <p class="section-label">Sources</p>
        <div
          class="upload-zone"
          :class="{ dragging: isDragging, 'has-file': uploadedDocs.length > 0 }"
          @click="triggerFileInput"
          @dragover.prevent="isDragging = true"
          @dragleave="isDragging = false"
          @drop.prevent="handleDrop"
        >
          <div class="upload-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="17 8 12 3 7 8"></polyline>
              <line x1="12" y1="3" x2="12" y2="15"></line>
            </svg>
          </div>
          <p class="upload-title">Add sources</p>
          <p class="upload-hint">PDF · TXT · MD &nbsp;·&nbsp; max 5 MB</p>
          <input
            ref="fileInputRef"
            type="file"
            accept=".pdf,.txt,.md"
            class="hidden-input"
            @change="handleFileSelect"
          />
        </div>

        <!-- Upload status -->
        <div v-if="uploadStatus" class="upload-status" :class="uploadStatus.type">
          <span class="status-dot"></span>
          {{ uploadStatus.message }}
        </div>
      </div>

      <!-- Document List -->
      <div class="sidebar-section flex-grow">
        <div class="section-label-row">
          <p class="section-label">Documents ({{ uploadedDocs.length }})</p>
          <button v-if="uploadedDocs.length > 0" class="clear-btn" @click="clearStore">Clear all</button>
        </div>

        <div v-if="uploadedDocs.length === 0" class="empty-docs">
          No sources yet. Upload a file to begin.
        </div>

        <ul v-else class="doc-list">
          <li v-for="doc in uploadedDocs" :key="doc.filename" class="doc-item">
            <span class="doc-icon">{{ getFileIcon(doc.filename) }}</span>
            <div class="doc-meta">
              <span class="doc-name">{{ doc.filename }}</span>
              <span class="doc-chunks">{{ doc.chunks_processed }} chunks</span>
            </div>
          </li>
        </ul>
      </div>

      <!-- Connection -->
      <div class="sidebar-footer">
        <span class="conn-dot" :class="wsConnected ? 'online' : 'offline'"></span>
        <span class="conn-label">{{ wsConnected ? 'Connected' : 'Reconnecting' }}</span>
      </div>
    </aside>

    <!-- ══════════════════ MAIN AREA ══════════════════ -->
    <main class="main-area">

      <!-- Top bar -->
      <header class="topbar">
        <div class="topbar-left">
          <span class="topbar-title">{{ currentDocTitle || 'Chat' }}</span>
          <span v-if="uploadedDocs.length > 0" class="topbar-badge">
            {{ uploadedDocs.length }} source{{ uploadedDocs.length > 1 ? 's' : '' }}
          </span>
        </div>
        <button class="clear-chat-btn" @click="clearChat">New chat</button>
      </header>

      <!-- Messages / content area -->
      <div ref="messagesContainer" class="messages-area">

        <!-- WELCOME STATE -->
        <div v-if="messages.length === 0 && !isAnalyzing && !documentSummary" class="welcome-screen">
          <div class="welcome-glyph">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="16 18 22 12 16 6"></polyline>
              <polyline points="8 6 2 12 8 18"></polyline>
            </svg>
          </div>
          <h2 class="welcome-title">DevAssist is ready</h2>
          <p class="welcome-sub">Ask anything about code, algorithms, system design, or debugging.<br>Upload a document on the left to unlock smart Q&amp;A.</p>
        </div>

        <!-- ANALYZING SPINNER -->
        <div v-if="isAnalyzing && messages.length === 0" class="analyzing-block">
          <div class="analyzing-spinner"></div>
          <p class="analyzing-text">Analyzing document...</p>
        </div>

        <!-- NOTEBOOK SUMMARY + CHIPS -->
        <div v-if="documentSummary && messages.length === 0" class="notebook-panel">
          <div class="nb-meta">
            <span class="nb-date">{{ todayFormatted }}</span>
            <span class="nb-sep">·</span>
            <span class="nb-source">{{ uploadedDocs.length }} source</span>
          </div>
          <div class="nb-summary" v-html="documentSummary"></div>
          <div v-if="suggestedQuestions.length > 0" class="nb-questions">
            <button
              v-for="(q, i) in suggestedQuestions"
              :key="i"
              class="nb-chip"
              @click="askSuggested(q)"
            >
              {{ q }}
            </button>
          </div>
        </div>

        <!-- CHAT MESSAGES -->
        <template v-for="(msg, i) in messages" :key="i">
          <div class="message-row" :class="msg.role">
            <div v-if="msg.role === 'assistant' || msg.role === 'error'" class="avatar assistant-avatar">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="16 18 22 12 16 6"></polyline>
                <polyline points="8 6 2 12 8 18"></polyline>
              </svg>
            </div>
            <div class="bubble" :class="msg.role">
              <div v-if="msg.role === 'assistant' || msg.role === 'error'" class="prose" v-html="renderMarkdown(msg.content)"></div>
              <div v-else class="user-text">{{ msg.content }}</div>
              <span v-if="msg.streaming" class="cursor-blink"></span>
            </div>
            <div v-if="msg.role === 'user'" class="avatar user-avatar">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                <circle cx="12" cy="7" r="4"></circle>
              </svg>
            </div>
          </div>
        </template>
      </div>

      <!-- Input bar -->
      <div class="input-bar">
        <textarea
          v-model="inputMessage"
          ref="inputRef"
          rows="1"
          placeholder="Ask a question or create something..."
          class="chat-input"
          :disabled="isGenerating"
          @keydown.enter.exact.prevent="sendMessage"
          @keydown.shift.enter="() => {}"
          @input="autoResize"
        ></textarea>
        <button
          class="send-btn"
          :class="{ active: inputMessage.trim() && !isGenerating }"
          :disabled="isGenerating || !inputMessage.trim()"
          @click="sendMessage"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
        </button>
      </div>
      <p class="input-note">Powered by Groq · llama-3.3-70b · RAG via FAISS</p>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, computed } from 'vue'
import { marked } from 'marked'
import hljs from 'highlight.js'

marked.setOptions({
  highlight(code, lang) {
    if (lang && hljs.getLanguage(lang)) return hljs.highlight(code, { language: lang }).value
    return hljs.highlightAuto(code).value
  },
  breaks: true,
})

// ALL STATE as ref() — avoids the reactive([]) length undefined bug
const messages           = ref([])
const inputMessage       = ref('')
const isGenerating       = ref(false)
const isDragging         = ref(false)
const uploadedDocs       = ref([])
const uploadStatus       = ref(null)
const wsConnected        = ref(false)
const isAnalyzing        = ref(false)
const documentSummary    = ref('')
const suggestedQuestions = ref([])

const messagesContainer  = ref(null)
const fileInputRef       = ref(null)
const inputRef           = ref(null)

const todayFormatted = computed(function() {
  return new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
})

const currentDocTitle = computed(function() {
  var docs = uploadedDocs.value
  if (!docs || docs.length === 0) return ''
  var name = docs[docs.length - 1].filename
  return name.replace(/\.[^.]+$/, '').replace(/_/g, ' ')
})

// WebSocket
var ws = null

function connectWebSocket() {
  var isSecure = window.location.protocol === 'https:'
  var WS_URL = (isSecure ? 'wss' : 'ws') + '://' + window.location.host + '/ws/chat'
  ws = new WebSocket(WS_URL)
  ws.onopen  = function() { wsConnected.value = true }
  ws.onclose = function() { wsConnected.value = false; setTimeout(connectWebSocket, 3000) }
  ws.onerror = function() {}
  ws.onmessage = function(event) { handleServerMessage(JSON.parse(event.data)) }
}

function handleServerMessage(data) {
  var msgs = messages.value
  if (data.status === 'streaming' && data.token) {
    var lastMsg = msgs[msgs.length - 1]
    if (lastMsg && lastMsg.role === 'assistant' && lastMsg.streaming) {
      lastMsg.content += data.token
    }
    scrollToBottom()
  } else if (data.status === 'done') {
    var last = msgs[msgs.length - 1]
    if (last) last.streaming = false
    isGenerating.value = false
    scrollToBottom()
    nextTick(function() { if (inputRef.value) inputRef.value.focus() })
  } else if (data.status === 'error') {
    var lastE = msgs[msgs.length - 1]
    if (lastE && lastE.streaming) {
      lastE.role = 'error'; lastE.content = data.message; lastE.streaming = false
    } else {
      messages.value.push({ role: 'error', content: data.message, streaming: false })
    }
    isGenerating.value = false
    scrollToBottom()
  }
}

function sendMessage() {
  var text = inputMessage.value.trim()
  if (!text || isGenerating.value || !ws || ws.readyState !== WebSocket.OPEN) return
  messages.value.push({ role: 'user', content: text, streaming: false })
  inputMessage.value = ''
  nextTick(function() { if (inputRef.value) inputRef.value.style.height = 'auto' })
  messages.value.push({ role: 'assistant', content: '', streaming: true })
  isGenerating.value = true
  scrollToBottom()
  ws.send(JSON.stringify({ message: text }))
}

function askSuggested(question) {
  inputMessage.value = question
  sendMessage()
}

function triggerFileInput() { if (fileInputRef.value) fileInputRef.value.click() }

function handleDrop(e) {
  isDragging.value = false
  var f = e.dataTransfer && e.dataTransfer.files[0]
  if (f) uploadFile(f)
}

function handleFileSelect(e) {
  var f = e.target.files && e.target.files[0]
  if (f) uploadFile(f)
  e.target.value = ''
}

async function uploadFile(file) {
  if (file.size > 5 * 1024 * 1024) {
    uploadStatus.value = { type: 'error', message: 'File exceeds 5 MB limit.' }
    return
  }
  uploadStatus.value = { type: 'loading', message: 'Uploading ' + file.name + '...' }
  var formData = new FormData()
  formData.append('file', file)
  try {
    var res  = await fetch('/upload', { method: 'POST', body: formData })
    var data = await res.json()
    if (res.ok && data.status === 'success') {
      uploadedDocs.value.push({ filename: data.filename, chunks_processed: data.chunks_processed })
      uploadStatus.value = { type: 'success', message: 'Indexed: ' + data.filename }
      setTimeout(function() { uploadStatus.value = null }, 4000)
      autoAnalyzeDocument()
    } else {
      uploadStatus.value = { type: 'error', message: data.detail || 'Upload failed.' }
    }
  } catch (err) {
    uploadStatus.value = { type: 'error', message: 'Cannot reach backend.' }
  }
}

async function autoAnalyzeDocument() {
  isAnalyzing.value = true
  documentSummary.value = ''
  suggestedQuestions.value = []
  try {
    var res  = await fetch('/generate-qa', { method: 'POST' })
    var data = await res.json()
    if (res.ok && data.status === 'success') {
      var docs    = uploadedDocs.value
      var docName = (data.document && data.document[0]) || (docs.length > 0 ? docs[docs.length - 1].filename : 'Document')
      var cleanName = docName.replace(/\.[^.]+$/, '').replace(/_/g, ' ')
      var pairs = data.qa_pairs || []
      var intro = pairs.slice(0, 2).map(function(p) { return p.answer }).join(' ')
      documentSummary.value = '<strong>' + cleanName + '</strong> — ' + intro
      suggestedQuestions.value = pairs.slice(0, 6).map(function(p) { return p.question })
    }
  } catch (e) {
    // silently fail
  }
  isAnalyzing.value = false
}

async function clearStore() {
  try {
    await fetch('/clear-store', { method: 'DELETE' })
    uploadedDocs.value       = []
    documentSummary.value    = ''
    suggestedQuestions.value = []
    messages.value           = []
    uploadStatus.value = { type: 'success', message: 'All sources cleared.' }
    setTimeout(function() { uploadStatus.value = null }, 3000)
  } catch (e) {}
}

function clearChat() {
  messages.value           = []
  documentSummary.value    = ''
  suggestedQuestions.value = []
}

function renderMarkdown(content) { return marked.parse(content || '') }

function scrollToBottom() {
  nextTick(function() {
    if (messagesContainer.value) messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  })
}

function getFileIcon(filename) {
  var ext = filename.split('.').pop().toLowerCase()
  return ext === 'pdf' ? '📕' : ext === 'md' ? '📝' : '📄'
}

function autoResize(e) {
  var el = e.target
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 160) + 'px'
}

onMounted(function() { connectWebSocket() })
onUnmounted(function() { if (ws) ws.close() })
</script>

<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');
@import 'highlight.js/styles/github-dark.css';

:root {
  --bg:          #0f1117;
  --surface:     #181c27;
  --surface-2:   #1e2335;
  --border:      rgba(255,255,255,0.07);
  --border-2:    rgba(255,255,255,0.12);
  --text:        #e8eaf0;
  --text-2:      #8b91a8;
  --text-3:      #555d7a;
  --accent:      #4f7fff;
  --accent-soft: rgba(79,127,255,0.12);
  --accent-2:    #6ee7b7;
  --danger:      #f87171;
  --radius:      12px;
  --radius-sm:   8px;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'DM Sans', sans-serif; background: var(--bg); color: var(--text); }
.app-shell { display: flex; height: 100vh; overflow: hidden; }

.sidebar {
  width: 280px; min-width: 280px; background: var(--surface);
  border-right: 1px solid var(--border); display: flex; flex-direction: column; overflow: hidden;
}
.sidebar-logo { display: flex; align-items: center; gap: 10px; padding: 20px 20px 16px; border-bottom: 1px solid var(--border); }
.logo-icon { width: 36px; height: 36px; border-radius: 10px; background: var(--accent); display: flex; align-items: center; justify-content: center; color: #fff; flex-shrink: 0; }
.logo-title { font-size: 15px; font-weight: 600; letter-spacing: -0.3px; color: var(--text); }
.logo-sub   { font-size: 11px; color: var(--text-3); margin-top: 1px; }
.sidebar-section { padding: 16px 16px 12px; border-bottom: 1px solid var(--border); }
.sidebar-section.flex-grow { flex: 1; overflow-y: auto; border-bottom: none; }
.section-label { font-size: 10.5px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-3); margin-bottom: 10px; }
.section-label-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.section-label-row .section-label { margin-bottom: 0; }
.clear-btn { font-size: 11px; color: var(--danger); background: none; border: none; cursor: pointer; opacity: 0.7; transition: opacity 0.15s; }
.clear-btn:hover { opacity: 1; }
.upload-zone { border: 1.5px dashed var(--border-2); border-radius: var(--radius); padding: 20px 12px; text-align: center; cursor: pointer; transition: all 0.2s; }
.upload-zone:hover, .upload-zone.dragging { border-color: var(--accent); background: var(--accent-soft); }
.upload-zone.has-file { border-style: solid; border-color: rgba(110,231,183,0.3); background: rgba(110,231,183,0.05); }
.upload-icon { color: var(--text-3); margin-bottom: 8px; display: flex; justify-content: center; }
.upload-title { font-size: 13px; font-weight: 500; color: var(--text-2); }
.upload-hint  { font-size: 11px; color: var(--text-3); margin-top: 4px; }
.hidden-input { display: none; }
.upload-status { margin-top: 10px; padding: 8px 12px; border-radius: var(--radius-sm); font-size: 11.5px; display: flex; align-items: center; gap: 7px; }
.upload-status.loading { background: rgba(79,127,255,0.1); color: #93b8ff; border: 1px solid rgba(79,127,255,0.2); }
.upload-status.success { background: rgba(110,231,183,0.1); color: var(--accent-2); border: 1px solid rgba(110,231,183,0.2); }
.upload-status.error   { background: rgba(248,113,113,0.1); color: var(--danger); border: 1px solid rgba(248,113,113,0.2); }
.status-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; background: currentColor; animation: pulse 1.5s ease-in-out infinite; }
.upload-status.success .status-dot, .upload-status.error .status-dot { animation: none; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
.empty-docs { font-size: 12px; color: var(--text-3); line-height: 1.6; font-style: italic; }
.doc-list { list-style: none; display: flex; flex-direction: column; gap: 6px; }
.doc-item { display: flex; align-items: flex-start; gap: 8px; padding: 9px 10px; border-radius: var(--radius-sm); background: var(--surface-2); border: 1px solid var(--border); }
.doc-icon { font-size: 15px; flex-shrink: 0; margin-top: 1px; }
.doc-meta { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.doc-name { font-size: 12px; font-weight: 500; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.doc-chunks { font-size: 10.5px; color: var(--text-3); }
.sidebar-footer { padding: 12px 16px; border-top: 1px solid var(--border); display: flex; align-items: center; gap: 7px; }
.conn-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.conn-dot.online  { background: var(--accent-2); }
.conn-dot.offline { background: var(--danger); }
.conn-label { font-size: 11.5px; color: var(--text-3); }

.main-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; background: var(--bg); }
.topbar { padding: 14px 28px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; background: var(--bg); flex-shrink: 0; }
.topbar-left { display: flex; align-items: center; gap: 10px; }
.topbar-title { font-size: 14px; font-weight: 600; color: var(--text); letter-spacing: -0.2px; }
.topbar-badge { font-size: 11px; background: var(--accent-soft); color: var(--accent); padding: 2px 9px; border-radius: 99px; border: 1px solid rgba(79,127,255,0.25); font-weight: 500; }
.clear-chat-btn { font-size: 12px; font-family: 'DM Sans', sans-serif; color: var(--text-3); background: none; border: 1px solid var(--border-2); border-radius: var(--radius-sm); padding: 5px 14px; cursor: pointer; transition: all 0.15s; }
.clear-chat-btn:hover { color: var(--text); background: var(--surface-2); }
.messages-area { flex: 1; overflow-y: auto; padding: 32px 28px 20px; display: flex; flex-direction: column; gap: 20px; scroll-behavior: smooth; }
.messages-area::-webkit-scrollbar { width: 4px; }
.messages-area::-webkit-scrollbar-track { background: transparent; }
.messages-area::-webkit-scrollbar-thumb { background: var(--border-2); border-radius: 4px; }

.welcome-screen { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; gap: 16px; padding-bottom: 60px; }
.welcome-glyph { width: 80px; height: 80px; border-radius: 24px; background: var(--surface); border: 1px solid var(--border-2); display: flex; align-items: center; justify-content: center; color: var(--accent); }
.welcome-title { font-size: 22px; font-weight: 600; letter-spacing: -0.5px; color: var(--text); }
.welcome-sub { font-size: 14px; color: var(--text-2); line-height: 1.65; max-width: 420px; }

.analyzing-block { display: flex; flex-direction: column; align-items: center; gap: 14px; padding: 48px 0; }
.analyzing-spinner { width: 32px; height: 32px; border: 2.5px solid var(--border-2); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.9s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.analyzing-text { font-size: 13px; color: var(--text-3); }

.notebook-panel { background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 24px 28px 20px; max-width: 760px; width: 100%; align-self: flex-start; animation: fadeUp 0.4s ease both; }
@keyframes fadeUp { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:translateY(0); } }
.nb-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
.nb-date { font-size: 11.5px; color: var(--text-3); font-weight: 500; }
.nb-sep  { color: var(--text-3); }
.nb-source { font-size: 11.5px; color: var(--accent); background: var(--accent-soft); padding: 1px 8px; border-radius: 99px; }
.nb-summary { font-size: 14px; line-height: 1.75; color: var(--text-2); margin-bottom: 20px; }
.nb-summary strong { color: var(--text); font-weight: 600; }
.nb-questions { display: flex; flex-direction: column; gap: 8px; }
.nb-chip { width: 100%; text-align: left; padding: 11px 16px; border-radius: var(--radius-sm); background: var(--surface-2); border: 1px solid var(--border); color: var(--text-2); font-family: 'DM Sans', sans-serif; font-size: 13px; cursor: pointer; transition: all 0.15s; }
.nb-chip:hover { border-color: var(--accent); color: var(--text); background: var(--accent-soft); }

.message-row { display: flex; align-items: flex-start; gap: 10px; }
.message-row.user { justify-content: flex-end; }
.message-row.assistant, .message-row.error { justify-content: flex-start; }
.avatar { width: 30px; height: 30px; border-radius: 9px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 2px; }
.assistant-avatar { background: var(--accent); color: #fff; }
.user-avatar { background: var(--surface-2); color: var(--text-2); border: 1px solid var(--border-2); }
.bubble { max-width: 72%; border-radius: 14px; padding: 12px 16px; font-size: 14px; line-height: 1.65; position: relative; }
.bubble.assistant { background: var(--surface); border: 1px solid var(--border); color: var(--text); border-radius: 14px 14px 14px 4px; }
.bubble.user { background: var(--accent); color: #fff; border-radius: 14px 14px 4px 14px; }
.bubble.error { background: rgba(248,113,113,0.08); border: 1px solid rgba(248,113,113,0.25); color: var(--danger); border-radius: 14px 14px 14px 4px; }
.user-text { white-space: pre-wrap; word-break: break-word; }
.cursor-blink { display: inline-block; width: 2px; height: 15px; background: var(--accent); margin-left: 4px; vertical-align: middle; border-radius: 2px; animation: blink 0.9s ease-in-out infinite; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }

.input-bar { margin: 0 28px 6px; display: flex; align-items: flex-end; gap: 10px; background: var(--surface); border: 1px solid var(--border-2); border-radius: 14px; padding: 10px 10px 10px 16px; transition: border-color 0.2s; }
.input-bar:focus-within { border-color: var(--accent); }
.chat-input { flex: 1; background: none; border: none; outline: none; resize: none; font-family: 'DM Sans', sans-serif; font-size: 14px; color: var(--text); line-height: 1.6; min-height: 24px; max-height: 160px; overflow-y: auto; }
.chat-input::placeholder { color: var(--text-3); }
.chat-input:disabled { opacity: 0.5; }
.send-btn { width: 36px; height: 36px; border-radius: 9px; border: none; background: var(--border-2); color: var(--text-3); cursor: not-allowed; display: flex; align-items: center; justify-content: center; transition: all 0.15s; flex-shrink: 0; }
.send-btn.active { background: var(--accent); color: #fff; cursor: pointer; }
.send-btn.active:hover { background: #6990ff; }
.input-note { text-align: center; font-size: 11px; color: var(--text-3); padding: 6px 0 12px; }

.prose { font-size: 14px; line-height: 1.7; color: var(--text); }
.prose pre { background: #0d1117 !important; border-radius: 10px; padding: 14px 16px; overflow-x: auto; margin: 10px 0; border: 1px solid var(--border); font-family: 'DM Mono', monospace; font-size: 12.5px; }
.prose code:not(pre code) { background: rgba(79,127,255,0.12); color: #93b8ff; border-radius: 5px; padding: 1px 6px; font-family: 'DM Mono', monospace; font-size: 12.5px; }
.prose p { margin-bottom: 8px; } .prose p:last-child { margin-bottom: 0; }
.prose ul { list-style: disc; padding-left: 20px; margin-bottom: 8px; }
.prose ol { list-style: decimal; padding-left: 20px; margin-bottom: 8px; }
.prose li { margin-bottom: 4px; }
.prose h1, .prose h2, .prose h3 { font-weight: 600; color: var(--text); margin: 12px 0 6px; }
.prose h1 { font-size: 18px; } .prose h2 { font-size: 16px; } .prose h3 { font-size: 14px; }
.prose a { color: var(--accent); text-decoration: underline; }
.prose blockquote { border-left: 3px solid var(--accent); padding-left: 12px; color: var(--text-2); font-style: italic; margin: 8px 0; }
.prose strong { font-weight: 600; color: var(--text); }
</style>