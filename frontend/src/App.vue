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

      <!-- Upload status -->
      <div v-if="uploadStatus" class="text-xs rounded p-2"
        :class="uploadStatus.type === 'error' ? 'bg-red-900/50 text-red-400' : 'bg-blue-900/50 text-blue-400'">
        {{ uploadStatus.msg }}
      </div>

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

              <!-- Doc info card: summary + suggested questions -->
              <div v-if="msg.type === 'doc-info'" class="bg-gray-800 rounded-xl p-5 border border-gray-700">
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

                <!-- Suggested questions — 10 chips, always visible -->
                <div v-if="msg.suggestions && msg.suggestions.length">
                  <p class="text-xs text-gray-500 uppercase tracking-widest mb-2">💡 Suggested Questions ({{ msg.suggestions.length }})</p>
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

                <!-- Generating indicator -->
                <div v-if="msg.generating" class="flex items-center gap-2 mt-3 text-xs text-gray-500">
                  <span class="w-2 h-2 bg-blue-400 rounded-full animate-pulse"></span>
                  Generating 10 questions from document…
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
const messages        = ref([])
const userInput       = ref('')
const connected       = ref(false)
const isTyping        = ref(false)
const streamingActive = ref(false)
const dragOver        = ref(false)
const uploadedDoc     = ref(null)
const uploadStatus    = ref(null)
const chatContainer   = ref(null)
const textareaHeight  = ref('48px')

let ws = null
let currentBotMsgIdx = -1

// ─── WebSocket ────────────────────────────────────────────
// Path MUST be /ws/chat — matches main.py @app.websocket("/ws/chat")
function connectWS() {
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
  ws = new WebSocket(protocol + '://' + location.host + '/ws/chat')

  ws.onopen  = () => { connected.value = true }
  ws.onclose = () => { connected.value = false; setTimeout(connectWS, 3000) }
  ws.onerror = () => { connected.value = false }

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      handleWsMessage(data)
    } catch (e) {}
  }
}

// ─── Handle WebSocket messages from main.py ───────────────
// main.py sends: { token, status: 'streaming' } | { status: 'done' } | { status: 'error', message }
function handleWsMessage(data) {
  if (data.status === 'streaming' && data.token) {
    // First token — create the bot message bubble
    if (!streamingActive.value) {
      isTyping.value = false
      streamingActive.value = true
      messages.value.push({ role: 'bot', content: '', streaming: true, type: 'text' })
      currentBotMsgIdx = messages.value.length - 1
    }
    // Append token to current message
    if (currentBotMsgIdx >= 0) {
      messages.value[currentBotMsgIdx].content += data.token
      scrollToBottom()
    }

  } else if (data.status === 'done') {
    if (currentBotMsgIdx >= 0) {
      messages.value[currentBotMsgIdx].streaming = false
    }
    streamingActive.value = false
    isTyping.value = false
    currentBotMsgIdx = -1
    scrollToBottom()

  } else if (data.status === 'error') {
    isTyping.value = false
    streamingActive.value = false
    if (currentBotMsgIdx >= 0) {
      messages.value[currentBotMsgIdx].content = '❌ ' + data.message
      messages.value[currentBotMsgIdx].streaming = false
      currentBotMsgIdx = -1
    } else {
      messages.value.push({ role: 'bot', content: '❌ ' + data.message, type: 'text' })
    }
    scrollToBottom()
  }
}

onMounted(connectWS)
onUnmounted(() => { if (ws) ws.close() })

// ─── Send Message ─────────────────────────────────────────
// main.py expects: { message: "text" }
function sendMessage() {
  const text = userInput.value.trim()
  if (!text || !connected.value || streamingActive.value) return

  messages.value.push({ role: 'user', content: text })
  userInput.value = ''
  textareaHeight.value = '48px'
  isTyping.value = true

  ws.send(JSON.stringify({ message: text }))
  scrollToBottom()
}

function askSuggestion(question) {
  if (!connected.value || streamingActive.value) return
  userInput.value = question
  sendMessage()
}

// ─── File Upload ──────────────────────────────────────────
function handleFileInput(e) {
  const file = e.target.files[0]
  if (file) uploadFile(file)
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

  uploadStatus.value = { type: 'info', msg: '⏳ Uploading document...' }

  const formData = new FormData()
  formData.append('file', file)

  try {
    // Step 1: Upload file — POST /upload (matches main.py)
    const uploadRes  = await fetch('/upload', { method: 'POST', body: formData })
    const uploadData = await uploadRes.json()

    if (!uploadRes.ok || uploadData.status !== 'success') {
      uploadStatus.value = { type: 'error', msg: uploadData.detail || 'Upload failed.' }
      return
    }

    uploadedDoc.value  = { name: file.name, size: formatBytes(file.size) }
    uploadStatus.value = { type: 'info', msg: '🧠 Generating 10 questions...' }

    // Add doc-info card immediately, with generating indicator
    const docCardIdx = messages.value.length
    messages.value.push({
      role:        'bot',
      type:        'doc-info',
      filename:    uploadData.filename,
      chunks:      uploadData.chunks_processed,
      suggestions: [],
      generating:  true,
    })
    scrollToBottom()

    // Step 2: Generate exactly 10 Q&A — POST /generate-qa (matches main.py)
    try {
      const qaRes  = await fetch('/generate-qa', { method: 'POST' })
      const qaData = await qaRes.json()

      if (qaRes.ok && qaData.status === 'success' && Array.isArray(qaData.qa_pairs)) {
        // Extract just the questions for the chips
        const questions = qaData.qa_pairs.map(function(p) { return p.question })
        messages.value[docCardIdx].suggestions = questions
      }
    } catch (e) {
      // Q&A generation failed silently — doc still works for chat
    }

    messages.value[docCardIdx].generating = false
    uploadStatus.value = null
    scrollToBottom()

  } catch (err) {
    uploadStatus.value = { type: 'error', msg: 'Upload error. Is the backend running?' }
  }
}

async function clearDocument() {
  uploadedDoc.value  = null
  uploadStatus.value = null
  try { await fetch('/clear-store', { method: 'DELETE' }) } catch (e) {}
}

// ─── Helpers ──────────────────────────────────────────────
function clearChat() { messages.value = [] }

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

function renderMarkdown(text) {
  if (!text) return ''
  return text
    .replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) =>
      '<pre class="bg-gray-900 rounded-lg p-3 my-2 overflow-x-auto text-xs"><code class="text-green-300">' + escapeHtml(code.trim()) + '</code></pre>')
    .replace(/`([^`]+)`/g,    '<code class="bg-gray-700 text-yellow-300 px-1 rounded text-xs">$1</code>')
    .replace(/\*\*(.+?)\*\*/g,'<strong class="text-white font-semibold">$1</strong>')
    .replace(/\*(.+?)\*/g,    '<em class="text-gray-300">$1</em>')
    .replace(/^### (.+)$/gm,  '<h3 class="text-sm font-semibold text-blue-300 mt-3 mb-1">$1</h3>')
    .replace(/^## (.+)$/gm,   '<h2 class="text-base font-semibold text-blue-300 mt-4 mb-2">$1</h2>')
    .replace(/^# (.+)$/gm,    '<h1 class="text-lg font-bold text-blue-300 mt-4 mb-2">$1</h1>')
    .replace(/^[-*] (.+)$/gm, '<li class="ml-4 list-disc text-gray-300 my-0.5">$1</li>')
    .replace(/\n/g,           '<br/>')
}

function escapeHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
}
</script>

<style>
#chat-messages::-webkit-scrollbar       { width: 6px; }
#chat-messages::-webkit-scrollbar-track { background: transparent; }
#chat-messages::-webkit-scrollbar-thumb { background: #374151; border-radius: 3px; }
.prose-custom li  { margin: 2px 0; }
.prose-custom pre { white-space: pre-wrap; }
</style>