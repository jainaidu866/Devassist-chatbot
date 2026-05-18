<template>
  <div class="flex h-screen bg-gray-950 text-gray-100 font-mono">
    <!-- Sidebar -->
    <aside class="w-72 bg-gray-900 border-r border-gray-800 flex flex-col p-4 gap-4">
      <!-- Header -->
      <div class="flex items-center gap-2 pb-3 border-b border-gray-800">
        <span class="text-blue-400 text-xl">⚡</span>
        <span class="text-lg font-bold text-white">DevAssist</span>
        <span
          class="ml-auto text-xs px-2 py-0.5 rounded-full"
          :class="connected ? 'bg-green-900 text-green-400' : 'bg-red-900 text-red-400'"
        >
          {{ connected ? '🟢 Connected' : '🔴 Disconnected' }}
        </span>
      </div>

      <!-- Upload Area -->
      <div>
        <p class="text-xs text-gray-500 uppercase tracking-widest mb-2">Document</p>
        <label
          class="flex flex-col items-center justify-center border-2 border-dashed border-gray-700 rounded-lg p-4 cursor-pointer hover:border-blue-500 transition-colors"
          :class="{ 'border-blue-500 bg-blue-950/20': dragOver }"
          @dragover.prevent="dragOver = true"
          @dragleave="dragOver = false"
          @drop.prevent="handleDrop"
        >
          <input type="file" class="hidden" accept=".pdf,.txt,.md" @change="handleFileInput" />
          <span class="text-2xl mb-1">📄</span>
          <span class="text-xs text-gray-400 text-center">
            Drop PDF, TXT, or MD<br /><span class="text-blue-400">or click to browse</span>
          </span>
        </label>
      </div>

      <!-- Uploaded Doc Info -->
      <div v-if="uploadedDoc" class="bg-gray-800 rounded-lg p-3 text-xs">
        <div class="flex items-center gap-2 mb-1">
          <span>📎</span>
          <span class="text-green-400 font-semibold truncate">{{ uploadedDoc.name }}</span>
        </div>
        <div class="text-gray-400">{{ uploadedDoc.size }}</div>
        <button
          class="mt-2 text-red-400 hover:text-red-300 text-xs"
          @click="clearDocument"
        >✕ Remove</button>
      </div>

      <!-- Upload status / processing indicator -->
      <div v-if="uploadStatus" class="text-xs rounded p-2"
        :class="uploadStatus.type === 'error' ? 'bg-red-900/50 text-red-400' : 'bg-blue-900/50 text-blue-400'">
        {{ uploadStatus.msg }}
      </div>

      <!-- Spacer -->
      <div class="flex-1"></div>

      <!-- Clear Chat -->
      <button
        @click="clearChat"
        class="w-full py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-400 text-xs transition-colors"
      >
        🗑 Clear Chat
      </button>
    </aside>

    <!-- Main Chat Area -->
    <main class="flex-1 flex flex-col overflow-hidden">
      <!-- Chat Messages -->
      <div
        ref="chatContainer"
        class="flex-1 overflow-y-auto p-6 space-y-4"
        id="chat-messages"
      >
        <!-- Welcome -->
        <div v-if="messages.length === 0" class="flex justify-center items-center h-full">
          <div class="text-center text-gray-600">
            <div class="text-5xl mb-4">⚡</div>
            <p class="text-xl font-semibold text-gray-400">DevAssist Chatbot</p>
            <p class="text-sm mt-2">Ask any programming question or upload a document to analyze it.</p>
          </div>
        </div>

        <!-- All Messages -->
        <div
          v-for="(msg, idx) in messages"
          :key="idx"
          class="flex"
          :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
        >
          <!-- Bot message -->
          <div v-if="msg.role === 'bot'" class="flex gap-3 max-w-3xl w-full">
            <div class="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-sm flex-shrink-0 mt-1">⚡</div>
            <div class="flex-1">

              <!-- Doc info card: summary + persistent suggested questions -->
              <div v-if="msg.type === 'doc-info'" class="bg-gray-800 rounded-xl p-5 border border-gray-700">
                <!-- Doc header -->
                <div class="flex items-center gap-2 mb-3 pb-3 border-b border-gray-700">
                  <span class="text-xl">📄</span>
                  <div>
                    <p class="font-semibold text-green-400 text-sm">Document Loaded</p>
                    <p class="text-xs text-gray-500">{{ msg.filename }}</p>
                  </div>
                  <span class="ml-auto text-xs text-gray-600 bg-gray-700 px-2 py-0.5 rounded-full">
                    {{ msg.chunks }} chunks
                  </span>
                </div>

                <!-- Real AI summary -->
                <div class="mb-4">
                  <p class="text-xs text-gray-500 uppercase tracking-widest mb-2">📋 Summary</p>
                  <div v-html="renderMarkdown(msg.content)" class="prose-custom text-sm text-gray-300 leading-relaxed"></div>
                </div>

                <!-- Smart suggested questions — ALWAYS VISIBLE, never removed -->
                <div v-if="msg.suggestions && msg.suggestions.length">
                  <p class="text-xs text-gray-500 uppercase tracking-widest mb-2">💡 Suggested Questions</p>
                  <div class="flex flex-col gap-2">
                    <button
                      v-for="(q, qi) in msg.suggestions"
                      :key="qi"
                      @click="askSuggestion(q)"
                      class="px-3 py-2 rounded-lg text-xs bg-blue-900/30 border border-blue-800/50 text-blue-300 hover:bg-blue-800/50 hover:text-white hover:border-blue-600 transition-all text-left"
                    >
                      <span class="text-blue-500 mr-1">›</span> {{ q }}
                    </button>
                  </div>
                </div>
              </div>

              <!-- Regular bot text message -->
              <div v-else class="bg-gray-800 rounded-xl px-4 py-3 border border-gray-700">
                <div v-html="renderMarkdown(msg.content)" class="prose-custom text-sm text-gray-200 leading-relaxed"></div>
                <span v-if="msg.streaming" class="inline-block w-2 h-4 bg-blue-400 animate-pulse ml-1 align-middle"></span>
              </div>

            </div>
          </div>

          <!-- User message -->
          <div v-if="msg.role === 'user'" class="max-w-xl">
            <div class="bg-blue-600 rounded-xl px-4 py-2.5 text-sm text-white break-words">
              {{ msg.content }}
            </div>
          </div>
        </div>

        <!-- Typing indicator -->
        <div v-if="isTyping && !streamingActive" class="flex gap-3">
          <div class="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-sm flex-shrink-0">⚡</div>
          <div class="bg-gray-800 rounded-xl px-4 py-3 border border-gray-700">
            <div class="flex gap-1 items-center h-4">
              <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay:0ms"></span>
              <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay:150ms"></span>
              <span class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay:300ms"></span>
            </div>
          </div>
        </div>
      </div>

      <!-- Input Area -->
      <div class="p-4 border-t border-gray-800 bg-gray-900 flex-shrink-0">
        <div class="flex gap-3 items-end max-w-4xl mx-auto">
          <textarea
            v-model="userInput"
            @keydown.enter.exact.prevent="sendMessage"
            @keydown.enter.shift.exact="userInput += '\n'"
            placeholder="Ask a programming question... (Enter to send, Shift+Enter for newline)"
            rows="1"
            class="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm text-gray-100 placeholder-gray-600 resize-none focus:outline-none focus:border-blue-500 transition-colors"
            :style="{ height: textareaHeight }"
            @input="adjustTextarea"
            :disabled="!connected"
          ></textarea>
          <button
            @click="sendMessage"
            :disabled="!userInput.trim() || !connected"
            class="px-4 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm transition-colors flex-shrink-0"
          >
            ➤
          </button>
        </div>
        <p class="text-center text-xs text-gray-700 mt-2">DevAssist answers programming questions only</p>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, onUnmounted } from 'vue'

// ─── State ────────────────────────────────────────────────
const messages       = ref([])
const userInput      = ref('')
const connected      = ref(false)
const isTyping       = ref(false)
const streamingActive = ref(false)
const dragOver       = ref(false)
const uploadedDoc    = ref(null)
const uploadStatus   = ref(null)
const chatContainer  = ref(null)
const textareaHeight = ref('48px')

let ws = null
let currentBotMsgIdx = -1

// ─── WebSocket ────────────────────────────────────────────
function connectWS() {
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
  ws = new WebSocket(`${protocol}://${location.host}/ws`)

  ws.onopen  = () => { connected.value = true }
  ws.onclose = () => { connected.value = false; setTimeout(connectWS, 3000) }
  ws.onerror = () => { connected.value = false }

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)

    if (data.type === 'start') {
      isTyping.value = false
      streamingActive.value = true
      // Append new bot message — never touch existing messages
      messages.value.push({ role: 'bot', content: '', streaming: true, type: 'text' })
      currentBotMsgIdx = messages.value.length - 1
      scrollToBottom()

    } else if (data.type === 'token') {
      if (currentBotMsgIdx >= 0) {
        messages.value[currentBotMsgIdx].content += data.content
        scrollToBottom()
      }

    } else if (data.type === 'end') {
      if (currentBotMsgIdx >= 0) {
        messages.value[currentBotMsgIdx].streaming = false
      }
      streamingActive.value = false
      isTyping.value = false
      currentBotMsgIdx = -1
      scrollToBottom()

    } else if (data.type === 'error') {
      isTyping.value = false
      streamingActive.value = false
      messages.value.push({ role: 'bot', content: `❌ ${data.content}`, type: 'text' })
      scrollToBottom()
    }
  }
}

onMounted(connectWS)
onUnmounted(() => { if (ws) ws.close() })

// ─── Send Message ─────────────────────────────────────────
// Only appends user message — never clears or modifies existing messages
function sendMessage() {
  const text = userInput.value.trim()
  if (!text || !connected.value) return

  messages.value.push({ role: 'user', content: text })
  userInput.value = ''
  textareaHeight.value = '48px'
  isTyping.value = true

  ws.send(JSON.stringify({ type: 'message', content: text }))
  scrollToBottom()
}

// ─── Click suggested question ─────────────────────────────
// Suggestions stay visible — we only append a user message and ask
function askSuggestion(question) {
  if (!connected.value) return
  messages.value.push({ role: 'user', content: question })
  isTyping.value = true
  ws.send(JSON.stringify({ type: 'message', content: question }))
  scrollToBottom()
}

// ─── File Upload ──────────────────────────────────────────
function handleFileInput(e) {
  const file = e.target.files[0]
  if (file) uploadFile(file)
  // Reset input so same file can be re-uploaded if needed
  e.target.value = ''
}

function handleDrop(e) {
  dragOver.value = false
  const file = e.dataTransfer.files[0]
  if (file) uploadFile(file)
}

async function uploadFile(file) {
  const ext = file.name.split('.').pop().toLowerCase()
  if (!['pdf', 'txt', 'md'].includes(ext)) {
    uploadStatus.value = { type: 'error', msg: 'Only PDF, TXT, MD files are allowed.' }
    return
  }
  if (file.size > 5 * 1024 * 1024) {
    uploadStatus.value = { type: 'error', msg: 'File too large (max 5MB).' }
    return
  }

  uploadStatus.value = { type: 'info', msg: '⏳ Uploading & analyzing document...' }

  const formData = new FormData()
  formData.append('file', file)

  try {
    const res  = await fetch('/upload', { method: 'POST', body: formData })
    const data = await res.json()

    if (data.status === 'ok') {
      uploadedDoc.value = { name: file.name, size: formatBytes(file.size) }
      uploadStatus.value = null

      // ── Append doc-info card with real summary + smart questions ──────────
      // This is a permanent message — it is NEVER removed or replaced
      messages.value.push({
        role:        'bot',
        type:        'doc-info',
        filename:    data.filename,
        chunks:      data.chunks,
        content:     data.summary,                // Real AI-generated summary from backend
        suggestions: data.suggested_questions,    // Smart context-aware questions from backend
      })

      scrollToBottom()
    } else {
      uploadStatus.value = { type: 'error', msg: data.detail || data.message || 'Upload failed.' }
    }
  } catch (err) {
    uploadStatus.value = { type: 'error', msg: 'Upload error. Is the backend running?' }
  }
}

function clearDocument() {
  uploadedDoc.value  = null
  uploadStatus.value = null
  fetch('/clear-document', { method: 'POST' }).catch(() => {})
}

// ─── Helpers ──────────────────────────────────────────────
function clearChat() {
  messages.value = []
}

function formatBytes(bytes) {
  if (bytes < 1024)        return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value)
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  })
}

function adjustTextarea(e) {
  e.target.style.height = '48px'
  e.target.style.height = Math.min(e.target.scrollHeight, 160) + 'px'
  textareaHeight.value  = e.target.style.height
}

// ─── Lightweight Markdown renderer ────────────────────────
function renderMarkdown(text) {
  if (!text) return ''
  return text
    .replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) =>
      `<pre class="bg-gray-900 rounded-lg p-3 my-2 overflow-x-auto text-xs"><code class="text-green-300">${escapeHtml(code.trim())}</code></pre>`)
    .replace(/`([^`]+)`/g,   '<code class="bg-gray-700 text-yellow-300 px-1 rounded text-xs">$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-white font-semibold">$1</strong>')
    .replace(/\*(.+?)\*/g,    '<em class="text-gray-300">$1</em>')
    .replace(/^### (.+)$/gm,  '<h3 class="text-sm font-semibold text-blue-300 mt-3 mb-1">$1</h3>')
    .replace(/^## (.+)$/gm,   '<h2 class="text-base font-semibold text-blue-300 mt-4 mb-2">$1</h2>')
    .replace(/^# (.+)$/gm,    '<h1 class="text-lg font-bold text-blue-300 mt-4 mb-2">$1</h1>')
    .replace(/^[-*] (.+)$/gm, '<li class="ml-4 list-disc text-gray-300 my-0.5">$1</li>')
    .replace(/\n/g,           '<br/>')
}

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}
</script>

<style>
#chat-messages::-webkit-scrollbar       { width: 6px; }
#chat-messages::-webkit-scrollbar-track { background: transparent; }
#chat-messages::-webkit-scrollbar-thumb { background: #374151; border-radius: 3px; }
.prose-custom li  { margin: 2px 0; }
.prose-custom pre { white-space: pre-wrap; }
</style>