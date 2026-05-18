<template>
  <div class="flex h-screen bg-gray-950 text-gray-100 font-mono overflow-hidden">

    <!-- ═══════════════════════ LEFT SIDEBAR ═══════════════════════ -->
    <aside class="w-72 min-w-[280px] bg-gray-900 border-r border-gray-800 flex flex-col">

      <!-- Logo -->
      <div class="px-5 py-4 border-b border-gray-800">
        <div class="flex items-center gap-2">
          <span class="text-2xl">⚙️</span>
          <div>
            <h1 class="text-base font-bold text-white leading-tight">DevAssist</h1>
            <p class="text-xs text-gray-500">Programming Assistant</p>
          </div>
        </div>
      </div>

      <!-- Upload Area -->
      <div class="px-4 py-5 border-b border-gray-800">
        <p class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
          📄 Upload Documentation
        </p>
        <div
          class="border-2 border-dashed border-gray-700 rounded-lg p-4 text-center cursor-pointer transition-all hover:border-blue-500 hover:bg-gray-800"
          :class="{ 'border-blue-500 bg-gray-800': isDragging }"
          @click="triggerFileInput"
          @dragover.prevent="isDragging = true"
          @dragleave="isDragging = false"
          @drop.prevent="handleDrop"
        >
          <div class="text-3xl mb-2">📂</div>
          <p class="text-xs text-gray-400">Click or drag & drop</p>
          <p class="text-xs text-gray-600 mt-1">.pdf · .txt · .md · max 5MB</p>
          <input
            ref="fileInputRef"
            type="file"
            accept=".pdf,.txt,.md"
            class="hidden"
            @change="handleFileSelect"
          />
        </div>

        <!-- Upload Status -->
        <div v-if="uploadStatus" class="mt-3">
          <div
            class="rounded-md px-3 py-2 text-xs flex items-start gap-2"
            :class="{
              'bg-blue-900/40 text-blue-300 border border-blue-800': uploadStatus.type === 'loading',
              'bg-green-900/40 text-green-300 border border-green-800': uploadStatus.type === 'success',
              'bg-red-900/40 text-red-300 border border-red-800': uploadStatus.type === 'error',
            }"
          >
            <span class="mt-0.5 shrink-0">
              {{ uploadStatus.type === 'loading' ? '⏳' : uploadStatus.type === 'success' ? '✅' : '❌' }}
            </span>
            <span>{{ uploadStatus.message }}</span>
          </div>
        </div>
      </div>

      <!-- Documents + Buttons + Q&A Panel -->
      <div class="flex-1 overflow-y-auto px-4 py-4">

        <p class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
          🗂️ Active Documents ({{ uploadedDocs.length }})
        </p>

        <div v-if="uploadedDocs.length === 0" class="text-xs text-gray-600 italic">
          No documents uploaded yet.<br>Upload a file to enable RAG context.
        </div>

        <!-- Document List -->
        <ul v-else class="space-y-2">
          <li
            v-for="doc in uploadedDocs"
            :key="doc.filename"
            class="bg-gray-800 rounded-md px-3 py-2 text-xs"
          >
            <div class="flex items-center gap-2">
              <span>{{ getFileIcon(doc.filename) }}</span>
              <span class="truncate text-gray-200 font-medium">{{ doc.filename }}</span>
            </div>
            <div class="mt-1 text-gray-500">{{ doc.chunks_processed }} chunks indexed</div>
          </li>
        </ul>

        <!-- Generate Q&A Button -->
        <button
          v-if="uploadedDocs.length > 0"
          class="mt-4 w-full text-xs rounded px-3 py-2 transition-colors font-semibold"
          :class="isGeneratingQA
            ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
            : 'bg-blue-700 hover:bg-blue-600 text-white cursor-pointer'"
          :disabled="isGeneratingQA"
          @click="generateQA"
        >
          {{ isGeneratingQA ? '⏳ Generating Q&A...' : '🧠 Generate Q&A from Doc' }}
        </button>

        <!-- Clear Documents Button -->
        <button
          v-if="uploadedDocs.length > 0"
          class="mt-2 w-full text-xs text-red-400 border border-red-900 rounded px-3 py-1.5 hover:bg-red-900/30 transition-colors"
          @click="clearStore"
        >
          🗑️ Clear All Documents
        </button>

        <!-- Q&A Generation Status -->
        <div v-if="qaStatus" class="mt-3">
          <div
            class="rounded-md px-3 py-2 text-xs"
            :class="{
              'bg-blue-900/40 text-blue-300 border border-blue-800': qaStatus.type === 'loading',
              'bg-green-900/40 text-green-300 border border-green-800': qaStatus.type === 'success',
              'bg-red-900/40 text-red-300 border border-red-800': qaStatus.type === 'error',
            }"
          >
            {{ qaStatus.message }}
          </div>
        </div>

        <!-- Q&A Results -->
        <div v-if="qaResults.length > 0" class="mt-4">
          <div class="flex items-center justify-between mb-2">
            <p class="text-xs font-semibold text-gray-400 uppercase tracking-wider">
              📋 Q&A Pairs ({{ qaResults.length }})
            </p>
            <button
              class="text-xs text-gray-600 hover:text-gray-400"
              @click="qaResults.splice(0, qaResults.length); qaStatus = null"
            >
              ✕ clear
            </button>
          </div>
          <div
            v-for="(qa, i) in qaResults"
            :key="i"
            class="bg-gray-800 rounded-md px-3 py-2 text-xs mb-2 space-y-1"
          >
            <p class="text-blue-300 font-semibold leading-relaxed">Q: {{ qa.question }}</p>
            <p class="text-gray-300 leading-relaxed">A: {{ qa.answer }}</p>
          </div>
        </div>

      </div>

      <!-- Connection Status -->
      <div class="px-4 py-3 border-t border-gray-800">
        <div class="flex items-center gap-2 text-xs">
          <div
            class="w-2 h-2 rounded-full"
            :class="wsConnected ? 'bg-green-400' : 'bg-red-500'"
          ></div>
          <span class="text-gray-500">{{ wsConnected ? 'Connected' : 'Disconnected' }}</span>
        </div>
      </div>
    </aside>

    <!-- ═══════════════════════ MAIN CHAT AREA ═══════════════════════ -->
    <main class="flex-1 flex flex-col overflow-hidden">

      <!-- Header -->
      <header class="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center justify-between shrink-0">
        <div>
          <h2 class="text-sm font-semibold text-white">Chat</h2>
          <p class="text-xs text-gray-500">
            {{ uploadedDocs.length > 0 ? `RAG active · ${uploadedDocs.length} doc(s)` : 'No documents — general mode' }}
          </p>
        </div>
        <button
          class="text-xs text-gray-500 hover:text-gray-300 border border-gray-700 rounded px-3 py-1 transition-colors"
          @click="clearChat"
        >
          Clear Chat
        </button>
      </header>

      <!-- Messages -->
      <div ref="messagesContainer" class="flex-1 overflow-y-auto px-6 py-4 space-y-4">

        <!-- Welcome -->
        <div v-if="messages.length === 0" class="flex justify-center items-center h-full">
          <div class="text-center text-gray-600 max-w-sm">
            <div class="text-5xl mb-4">💻</div>
            <h3 class="text-lg font-semibold text-gray-400 mb-2">DevAssist is ready</h3>
            <p class="text-sm">Ask me anything about code, algorithms, system design, or debugging.</p>
            <p class="text-xs mt-2 text-gray-700">Upload a PDF/TXT doc to enable RAG context.</p>
          </div>
        </div>

        <!-- Message Bubbles -->
        <div
          v-for="(msg, i) in messages"
          :key="i"
          class="flex gap-3"
          :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
        >
          <div v-if="msg.role === 'assistant'" class="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-sm shrink-0 mt-1">
            ⚙
          </div>

          <div
            class="max-w-[75%] rounded-xl px-4 py-3 text-sm leading-relaxed"
            :class="{
              'bg-blue-600 text-white rounded-br-sm': msg.role === 'user',
              'bg-gray-800 text-gray-100 rounded-bl-sm': msg.role === 'assistant',
              'bg-red-900/50 text-red-300 border border-red-800': msg.role === 'error',
            }"
          >
            <div
              v-if="msg.role === 'assistant' || msg.role === 'error'"
              class="prose prose-invert prose-sm max-w-none"
              v-html="renderMarkdown(msg.content)"
            ></div>
            <div v-else class="whitespace-pre-wrap break-words">{{ msg.content }}</div>
            <span v-if="msg.streaming" class="inline-block w-1.5 h-4 bg-blue-400 ml-1 animate-pulse align-middle"></span>
          </div>

          <div v-if="msg.role === 'user'" class="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center text-sm shrink-0 mt-1">
            👤
          </div>
        </div>
      </div>

      <!-- Input Area -->
      <div class="bg-gray-900 border-t border-gray-800 px-6 py-4 shrink-0">
        <div class="flex gap-3 items-end">
          <textarea
            v-model="inputMessage"
            ref="inputRef"
            rows="1"
            placeholder="Ask a programming question... (Shift+Enter for newline)"
            class="flex-1 bg-gray-800 text-gray-100 placeholder-gray-600 rounded-xl px-4 py-3 text-sm resize-none border border-gray-700 focus:outline-none focus:border-blue-500 transition-colors"
            :disabled="isGenerating"
            style="min-height: 48px; max-height: 160px; overflow-y: auto;"
            @keydown.enter.exact.prevent="sendMessage"
            @keydown.shift.enter="() => {}"
          ></textarea>
          <button
            class="px-5 py-3 rounded-xl text-sm font-semibold transition-all shrink-0"
            :class="isGenerating || !inputMessage.trim()
              ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-500 text-white cursor-pointer'"
            :disabled="isGenerating || !inputMessage.trim()"
            @click="sendMessage"
          >
            {{ isGenerating ? '⏳' : '➤ Send' }}
          </button>
        </div>
        <p class="text-xs text-gray-700 mt-2">
          Programming questions only · Powered by Groq llama3-70b · RAG via FAISS
        </p>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, nextTick } from 'vue'
import { marked } from 'marked'
import hljs from 'highlight.js'

// ── Markdown setup ────────────────────────────────────────────────────────────
marked.setOptions({
  highlight(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value
    }
    return hljs.highlightAuto(code).value
  },
  breaks: true,
})

// ── State ─────────────────────────────────────────────────────────────────────
const messages        = reactive([])
const inputMessage    = ref('')
const isGenerating    = ref(false)
const isDragging      = ref(false)
const uploadedDocs    = reactive([])
const uploadStatus    = ref(null)
const wsConnected     = ref(false)
const qaResults       = reactive([])
const isGeneratingQA  = ref(false)
const qaStatus        = ref(null)

const messagesContainer = ref(null)
const fileInputRef      = ref(null)
const inputRef          = ref(null)

// ── WebSocket ─────────────────────────────────────────────────────────────────
let ws = null

function connectWebSocket() {
  const isSecure = window.location.protocol === 'https:'
  const WS_URL = `${isSecure ? 'wss' : 'ws'}://${window.location.host}/ws/chat`

  ws = new WebSocket(WS_URL)

  ws.onopen = () => {
    wsConnected.value = true
    console.log('✅ WebSocket connected')
  }

  ws.onclose = () => {
    wsConnected.value = false
    setTimeout(connectWebSocket, 3000)
  }

  ws.onerror = () => {}

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    handleServerMessage(data)
  }
}

function handleServerMessage(data) {
  if (data.status === 'streaming' && data.token) {
    const lastMsg = messages[messages.length - 1]
    if (lastMsg && lastMsg.role === 'assistant' && lastMsg.streaming) {
      lastMsg.content += data.token
    }
    scrollToBottom()
  } else if (data.status === 'done') {
    const lastMsg = messages[messages.length - 1]
    if (lastMsg) lastMsg.streaming = false
    isGenerating.value = false
    scrollToBottom()
    nextTick(() => inputRef.value?.focus())
  } else if (data.status === 'error') {
    const lastMsg = messages[messages.length - 1]
    if (lastMsg && lastMsg.streaming) {
      lastMsg.role = 'error'
      lastMsg.content = data.message
      lastMsg.streaming = false
    } else {
      messages.push({ role: 'error', content: data.message, streaming: false })
    }
    isGenerating.value = false
    scrollToBottom()
  }
}

// ── Send Message ──────────────────────────────────────────────────────────────
async function sendMessage() {
  const text = inputMessage.value.trim()
  if (!text || isGenerating.value || !ws || ws.readyState !== WebSocket.OPEN) return

  messages.push({ role: 'user', content: text, streaming: false })
  inputMessage.value = ''
  messages.push({ role: 'assistant', content: '', streaming: true })
  isGenerating.value = true
  scrollToBottom()
  ws.send(JSON.stringify({ message: text }))
}

// ── File Upload ───────────────────────────────────────────────────────────────
function triggerFileInput() { fileInputRef.value?.click() }

function handleDrop(e) {
  isDragging.value = false
  const file = e.dataTransfer?.files[0]
  if (file) uploadFile(file)
}

function handleFileSelect(e) {
  const file = e.target.files?.[0]
  if (file) uploadFile(file)
  e.target.value = ''
}

async function uploadFile(file) {
  if (file.size > 5 * 1024 * 1024) {
    uploadStatus.value = { type: 'error', message: 'File exceeds 5MB limit.' }
    return
  }

  uploadStatus.value = { type: 'loading', message: `Uploading ${file.name}...` }

  const formData = new FormData()
  formData.append('file', file)

  try {
    const res = await fetch('/upload', { method: 'POST', body: formData })
    const data = await res.json()

    if (res.ok && data.status === 'success') {
      uploadedDocs.push({ filename: data.filename, chunks_processed: data.chunks_processed })
      uploadStatus.value = {
        type: 'success',
        message: `✓ ${data.filename} — ${data.chunks_processed} chunks indexed`,
      }
    } else {
      uploadStatus.value = { type: 'error', message: data.detail || 'Upload failed.' }
    }
  } catch {
    uploadStatus.value = { type: 'error', message: 'Cannot reach backend.' }
  }

  setTimeout(() => { uploadStatus.value = null }, 5000)
}

// ── Generate Q&A ──────────────────────────────────────────────────────────────
async function generateQA() {
  isGeneratingQA.value = true
  qaStatus.value = { type: 'loading', message: '⏳ Generating Q&A pairs... (may take 30-60 seconds)' }
  qaResults.splice(0, qaResults.length)

  try {
    const res = await fetch('/generate-qa', { method: 'POST' })
    const data = await res.json()

    if (res.ok && data.status === 'success') {
      qaResults.push(...data.qa_pairs)
      qaStatus.value = {
        type: 'success',
        message: `✅ ${data.total_qa_pairs} Q&A pairs generated!`,
      }
    } else {
      qaStatus.value = { type: 'error', message: data.detail || 'Failed to generate Q&A.' }
    }
  } catch {
    qaStatus.value = { type: 'error', message: 'Cannot reach backend.' }
  }

  isGeneratingQA.value = false
  setTimeout(() => { qaStatus.value = null }, 5000)
}

// ── Clear Store ───────────────────────────────────────────────────────────────
async function clearStore() {
  try {
    await fetch('/clear-store', { method: 'DELETE' })
    uploadedDocs.splice(0, uploadedDocs.length)
    qaResults.splice(0, qaResults.length)
    qaStatus.value = null
    uploadStatus.value = { type: 'success', message: 'All documents cleared.' }
    setTimeout(() => { uploadStatus.value = null }, 3000)
  } catch {}
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function renderMarkdown(content) { return marked.parse(content || '') }

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

function clearChat() { messages.splice(0, messages.length) }

function getFileIcon(filename) {
  const ext = filename.split('.').pop().toLowerCase()
  return ext === 'pdf' ? '📕' : ext === 'md' ? '📝' : '📄'
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────
onMounted(() => { connectWebSocket() })
onUnmounted(() => { ws?.close() })
</script>

<style>
@import 'highlight.js/styles/github-dark.css';

.prose pre {
  @apply rounded-lg overflow-x-auto my-2 text-xs;
  background: #0d1117 !important;
  padding: 1rem;
}
.prose code:not(pre code) {
  @apply bg-gray-700 text-blue-300 rounded px-1 py-0.5 text-xs;
}
.prose p { @apply mb-2 last:mb-0; }
.prose ul { @apply list-disc list-inside mb-2 space-y-1; }
.prose ol { @apply list-decimal list-inside mb-2 space-y-1; }
.prose h1, .prose h2, .prose h3 { @apply font-bold text-white mb-2 mt-3; }
.prose a { @apply text-blue-400 underline; }
.prose blockquote { @apply border-l-4 border-blue-500 pl-3 italic text-gray-400; }
</style>