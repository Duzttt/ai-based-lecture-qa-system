<script setup>
import { ref, computed, onMounted } from 'vue'
import { useDocumentStore } from '../../stores/documentStore'
import RetrievalChunks from './RetrievalChunks.vue'
import PdfViewer from '../documents/PdfViewer.vue'
import BidirectionalCitations from '../shared/BidirectionalCitations.vue'
import QuestionSuggestions from './QuestionSuggestions.vue'
import CitationAnswer from './CitationAnswer.vue'

const documentStore = useDocumentStore()

const messages = ref([])
const question = ref('')
const isLoading = ref(false)
const error = ref('')
const lastRetrievedChunks = ref([])
const isRetrieving = ref(false)

// PDF Viewer state
const showPdfViewer = ref(false)
const currentPdfUrl = ref('')
const currentPdfPage = ref(1)
const currentHighlightText = ref('')

// Bidirectional citations state
const showBidirectionalPanel = ref(false)
const selectedCitation = ref({ source: '', page: null, text: '' })
const showDocumentListTooltip = ref(false)

// Build bidirectional citations index
const bidirectionalIndex = ref({})

// Computed
const selectedSources = computed(() => documentStore.selectedDocIds)
const selectedCount = computed(() => documentStore.selectedCount)
const selectedDocuments = computed(() => documentStore.selectedDocuments)
const hasSelection = computed(() => documentStore.hasSelection)

const sendMessage = async () => {
  if (!question.value.trim()) return

  const userQuestion = question.value
  const userMsgIndex = messages.value.length

  messages.value.push({
    role: 'user',
    content: userQuestion,
    id: `msg_user_${Date.now()}_${userMsgIndex}`,
  })
  question.value = ''
  isLoading.value = true
  isRetrieving.value = true
  error.value = ''
  lastRetrievedChunks.value = []

  try {
    const payload = { query: userQuestion }

    // Add selected document sources for filtering
    if (selectedSources.value && selectedSources.value.length > 0) {
      payload.sources = selectedSources.value
    }

    const response = await fetch('/api/chat/citations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || errorData.error || 'Failed to get response')
    }

    const data = await response.json()
    
    // Handle new citation format
    const sentences = data.sentences || []
    const sources = data.sources || {}
    const chunks = data.retrieved_chunks || []

    // Build answer text from sentences for display
    const answerText = sentences.map(s => s.text).join(' ') || 'No answer received.'

    messages.value.push({
      role: 'assistant',
      content: answerText,
      sentences: sentences,
      sources: sources,
      chunks: chunks,
      id: `msg_${Date.now()}`
    })

    // Register citations for bidirectional tracing
    registerCitations(messages.value[messages.value.length - 1].id, userQuestion, answerText, chunks)

    lastRetrievedChunks.value = chunks
  } catch (err) {
    error.value = err.message
  } finally {
    isLoading.value = false
    isRetrieving.value = false
  }
}

const getMessageCitationTitle = (msg) => {
  if (!msg || msg.role !== 'assistant' || !msg.chunks || !msg.chunks.length) {
    return ''
  }
  const sources = Array.from(
    new Set(
      msg.chunks
        .map((c) => c.source)
        .filter((s) => typeof s === 'string' && s.trim()),
    ),
  )
  if (!sources.length) return ''
  return `Supported by: ${sources.join(', ')}`
}

const registerCitations = (messageId, query, answer, chunks) => {
  chunks.forEach(chunk => {
    const key = `${chunk.source}_${chunk.page}_${(chunk.text || '').substring(0, 50)}`
    if (!bidirectionalIndex.value[key]) {
      bidirectionalIndex.value[key] = []
    }
    bidirectionalIndex.value[key].push({
      messageId,
      query,
      answer: answer.substring(0, 150) + (answer.length > 150 ? '...' : ''),
      timestamp: new Date().toLocaleTimeString(),
      source: chunk.source,
      page: chunk.page,
      text: chunk.text
    })
  })
}

const handleKeyPress = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

const handleChunkHover = (chunk) => {
  console.log('Chunk hover:', chunk)
}

const handleChunkClick = (chunk) => {
  console.log('Chunk clicked:', chunk)
  if (chunk.source) {
    currentPdfUrl.value = '/media/data_source/' + encodeURIComponent(chunk.source)
    currentPdfPage.value = chunk.page || 1
    currentHighlightText.value = chunk.text?.substring(0, 50) || ''
    showPdfViewer.value = true
  }
}

const handleChunkRightClick = (event, chunk) => {
  event.preventDefault()
  const key = `${chunk.source}_${chunk.page}_${(chunk.text || '').substring(0, 50)}`
  const citations = bidirectionalIndex.value[key] || []
  if (citations.length > 0) {
    selectedCitation.value = {
      source: chunk.source,
      page: chunk.page,
      text: chunk.text
    }
    showBidirectionalPanel.value = true
  }
}

const closePdfViewer = () => {
  showPdfViewer.value = false
  currentPdfUrl.value = ''
  currentPdfPage.value = 1
  currentHighlightText.value = ''
}

const closeBidirectionalPanel = () => {
  showBidirectionalPanel.value = false
  selectedCitation.value = { source: '', page: null, text: '' }
}

const navigateToMessage = (messageId) => {
  setTimeout(() => {
    const element = document.querySelector(`[data-message-id="${messageId}"]`)
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' })
      element.style.animation = 'none'
      element.offsetHeight // trigger reflow
      element.style.animation = 'highlightMessage 1s ease'
    }
  }, 100)
}

const toggleDocumentListTooltip = () => {
  showDocumentListTooltip.value = !showDocumentListTooltip.value
}

const onChunkRightClick = handleChunkRightClick

// Handle suggested question click
const handleSuggestionSelect = (questionText) => {
  // Fill the question into input and send
  question.value = questionText
  sendMessage()
}
</script>

<template>
  <div class="panel chat-panel">
    <div class="chat-header">
      <div class="chat-title">
        <span class="chat-title-main">Chat</span>
        <span class="chat-title-sub">Ask anything about your notes</span>
      </div>
      
      <!-- Retrieval Scope Indicator -->
      <div v-if="hasSelection" class="retrieval-scope" @click="toggleDocumentListTooltip">
        <span class="scope-icon">🔍</span>
        <span class="scope-label">Retrieval scope:</span>
        <span class="scope-value">
          {{ selectedCount }} selected document{{ selectedCount > 1 ? 's' : '' }}
          <svg class="scope-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M6 9l6 6 6-6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </span>
        
        <!-- Document List Tooltip -->
        <div v-if="showDocumentListTooltip" class="document-tooltip" @click.stop>
          <div class="tooltip-header">
            <span>📄 Selected documents</span>
            <button class="tooltip-close" @click="showDocumentListTooltip = false">✕</button>
          </div>
          <div class="tooltip-content">
            <div 
              v-for="doc in selectedDocuments" 
              :key="doc.name || doc.filename"
              class="tooltip-doc-item"
            >
              <span class="doc-icon">📄</span>
              <span class="doc-name" :title="doc.name || doc.filename">
                {{ doc.name || doc.filename }}
              </span>
            </div>
          </div>
          <div class="tooltip-footer">
            <span class="footer-note">Click the Sources panel to change selection</span>
          </div>
        </div>
      </div>
      
      <div v-else class="retrieval-scope empty">
        <span class="scope-icon">⚠️</span>
        <span class="scope-label">No documents selected</span>
      </div>
    </div>
    
    <div class="chat-body">
      <div v-if="messages.length === 0" class="chat-empty-card">
        <div class="chat-empty-icon">💬</div>
        <div class="chat-empty-title">Start a Conversation</div>
        <div class="chat-empty-desc">Ask questions about your lecture notes</div>
        <div v-if="!hasSelection" class="empty-warning">
          <span class="warning-icon">⚠️</span>
          <span class="warning-text">Please select documents to search on the left</span>
        </div>
      </div>
      <div v-else class="messages-list">
        <div
          v-for="(msg, idx) in messages"
          :key="idx"
          class="message-group"
          :data-message-id="msg.id"
        >
          <div class="message" :class="msg.role">
            <div class="message-avatar">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
            <div
              class="message-content"
              :class="{
                'has-citations': msg.role === 'assistant' && msg.chunks && msg.chunks.length > 0
              }"
              :title="getMessageCitationTitle(msg)"
            >
              <!-- Use CitationAnswer component if sentences are available -->
              <CitationAnswer
                v-if="msg.role === 'assistant' && msg.sentences && msg.sentences.length > 0"
                :sentences="msg.sentences"
                :sources="msg.sources"
                :show-tooltip="true"
              />
              <!-- Fallback to plain text -->
              <template v-else>
                {{ msg.content }}
              </template>
            </div>
          </div>

          <!-- Show retrieved chunks for assistant messages -->
          <div v-if="msg.role === 'assistant' && msg.chunks && msg.chunks.length > 0" class="retrieval-section">
            <RetrievalChunks
              :chunks="msg.chunks"
              :loading="false"
              @chunk-hover="handleChunkHover"
              @chunk-click="handleChunkClick"
              @chunk-rightclick="handleChunkRightClick"
            />
          </div>
        </div>
        <div v-if="isLoading" class="message-group">
          <div class="message assistant">
            <div class="message-avatar">🤖</div>
            <div class="message-content loading">Thinking...</div>
          </div>
          <div v-if="isRetrieving" class="retrieval-section">
            <RetrievalChunks :chunks="[]" :loading="true" />
          </div>
        </div>
      </div>
    </div>
    
    <!-- Question Suggestions -->
    <div class="chat-suggestions-wrap">
      <QuestionSuggestions
        :selected-documents="selectedDocuments"
        :disabled="isLoading"
        @question-select="handleSuggestionSelect"
      />
    </div>
    
    <div class="chat-input-wrap">
      <input
        v-model="question"
        @keydown.enter.prevent="sendMessage"
        type="text"
        class="chat-input"
        placeholder="Ask a question..."
        :disabled="isLoading"
      />
      <button
        class="chat-send-btn"
        @click="sendMessage"
        :disabled="isLoading || !question.trim()"
      >
        ➤
      </button>
    </div>
    <div v-if="error" class="chat-error">{{ error }}</div>

    <!-- PDF Viewer Panel -->
    <PdfViewer
      :show="showPdfViewer"
      :pdf-url="currentPdfUrl"
      :target-page="currentPdfPage"
      :highlight-text="currentHighlightText"
      @close="closePdfViewer"
    />

    <!-- Bidirectional Citations Panel -->
    <BidirectionalCitations
      :show="showBidirectionalPanel"
      :source="selectedCitation.source"
      :page="selectedCitation.page"
      :text="selectedCitation.text"
      :citations="bidirectionalIndex[selectedCitation.source + '_' + selectedCitation.page + '_' + (selectedCitation.text || '').substring(0, 50)] || []"
      @close="closeBidirectionalPanel"
      @navigate-to-message="navigateToMessage"
    />
  </div>
</template>

<style scoped>
@keyframes highlightMessage {
  0% { background: rgba(99, 102, 241, 0.3); }
  100% { background: transparent; }
}

.chat-panel {
  position: relative;
  background: linear-gradient(
    135deg,
    rgba(15, 25, 45, 0.4) 0%,
    rgba(25, 35, 60, 0.5) 100%
  );
  border-radius: var(--radius-lg);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-top-color: rgba(255, 255, 255, 0.12);
  border-left-color: rgba(255, 255, 255, 0.12);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
  min-height: 0;
  height: 100%;
  backdrop-filter: blur(15px) saturate(180%);
  -webkit-backdrop-filter: blur(15px) saturate(180%);
  box-shadow:
    0 15px 30px -15px rgba(0, 0, 0, 0.6),
    inset 0 1px 1px rgba(255, 255, 255, 0.1),
    inset 0 -2px 2px rgba(0, 0, 0, 0.2);
}

.chat-header {
  padding: 10px 14px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.9);
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.chat-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.chat-title-main {
  font-size: 13px;
  font-weight: 600;
}

.chat-title-sub {
  font-size: 11px;
  color: var(--text-muted);
}

/* Retrieval Scope Indicator */
.retrieval-scope {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.15);
  border: 1px solid rgba(99, 102, 241, 0.3);
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  white-space: nowrap;
}

.retrieval-scope:hover {
  background: rgba(99, 102, 241, 0.2);
  border-color: var(--accent);
}

.retrieval-scope.empty {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.3);
  cursor: default;
}

.retrieval-scope.empty:hover {
  background: rgba(239, 68, 68, 0.15);
}

.scope-icon {
  font-size: 12px;
}

.scope-label {
  font-size: 10px;
  color: var(--text-muted);
}

.scope-value {
  font-size: 11px;
  color: var(--accent);
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 3px;
}

.scope-chevron {
  width: 12px;
  height: 12px;
  color: var(--text-muted);
  transition: transform 0.2s;
}

.retrieval-scope:hover .scope-chevron {
  transform: rotate(180deg);
}

/* Document Tooltip */
.document-tooltip {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 280px;
  max-height: 300px;
  background: rgba(15, 23, 42, 0.98);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 12px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6);
  z-index: 100;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  animation: slideUp 0.2s ease;
}

.tooltip-header {
  padding: 10px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-main);
  background: rgba(255, 255, 255, 0.02);
}

.tooltip-close {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  transition: all 0.2s;
}

.tooltip-close:hover {
  background: rgba(255, 255, 255, 0.1);
  color: white;
}

.tooltip-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tooltip-doc-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
  font-size: 11px;
  color: var(--text-main);
  transition: all 0.2s;
}

.tooltip-doc-item:hover {
  background: rgba(99, 102, 241, 0.15);
}

.doc-icon {
  font-size: 14px;
}

.doc-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tooltip-footer {
  padding: 8px 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(0, 0, 0, 0.2);
}

.footer-note {
  font-size: 10px;
  color: var(--text-muted);
  font-style: italic;
}

.chat-body {
  flex: 1;
  padding: 14px;
  overflow-y: auto;
  position: relative;
  min-height: 0;
}

.chat-empty-card {
  margin: 0 auto;
  margin-top: 10%;
  max-width: 260px;
  text-align: center;
  padding: 16px 14px 18px;
  border-radius: 18px;
  background: linear-gradient(
    145deg,
    rgba(25, 35, 55, 0.5) 0%,
    rgba(15, 25, 45, 0.6) 100%
  );
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-top-color: rgba(255, 255, 255, 0.2);
  border-left-color: rgba(255, 255, 255, 0.2);
  box-shadow:
    0 25px 40px -20px black,
    inset -2px -2px 5px rgba(0, 0, 0, 0.3),
    inset 2px 2px 5px rgba(255, 255, 255, 0.1);
}

.chat-empty-icon {
  width: 40px;
  height: 40px;
  border-radius: 16px;
  margin: 0 auto 10px;
  background: radial-gradient(circle at 20% 0, #a855f7, #22c55e);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #020617;
  font-size: 20px;
}

.chat-empty-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 4px;
}

.chat-empty-desc {
  font-size: 12px;
  color: var(--text-muted);
}

.empty-warning {
  margin-top: 12px;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.warning-icon {
  font-size: 14px;
}

.warning-text {
  font-size: 11px;
  color: #fca5a5;
}

.messages-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.message {
  display: flex;
  gap: 10px;
  padding: 12px;
  border-radius: 12px;
  max-width: 85%;
}

.message.user {
  align-self: flex-end;
  background: rgba(99, 102, 241, 0.2);
  border: 1px solid rgba(99, 102, 241, 0.3);
  margin-left: auto;
}

.message.assistant {
  align-self: flex-start;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.message-avatar {
  font-size: 18px;
  flex-shrink: 0;
}

.message-content {
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-main);
}

.message-content.has-citations {
  position: relative;
  border-bottom: 1px dotted rgba(148, 163, 184, 0.8);
  padding-bottom: 2px;
  cursor: help;
}

.message-content.loading {
  color: var(--text-muted);
  font-style: italic;
}

.retrieval-section {
  width: 100%;
  max-width: 100%;
  margin-top: 8px;
}

.chat-suggestions-wrap {
  padding: 0 14px;
}

.chat-input-wrap {
  padding: 10px 14px 12px;
  border-top: 1px solid rgba(31, 41, 55, 0.9);
  display: flex;
  gap: 8px;
  align-items: center;
  position: sticky;
  bottom: 0;
  z-index: 5;
  background: rgba(15, 23, 42, 0.85);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}

.chat-input {
  flex: 1;
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid rgba(55, 65, 81, 0.9);
  background: #020617;
  color: var(--text-main);
  font-size: 13px;
  outline: none;
  transition: all 0.2s;
}

.chat-input:focus {
  border-color: var(--accent);
}

.chat-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chat-send-btn {
  width: 32px;
  height: 32px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: linear-gradient(
    145deg,
    rgba(99, 102, 241, 0.8) 0%,
    rgba(139, 92, 246, 0.9) 100%
  );
  color: #f9fafb;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 14px;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  box-shadow:
    0 5px 15px -5px rgba(99, 102, 241, 0.3),
    inset 0 1px 2px rgba(255, 255, 255, 0.3);
  transition: all 0.2s ease;
}

.chat-send-btn:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow:
    0 8px 20px -5px rgba(99, 102, 241, 0.5),
    inset 0 1px 3px rgba(255, 255, 255, 0.4);
}

.chat-send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.chat-error {
  margin: 4px 14px 0;
  min-height: 1.2em;
  font-size: 11px;
  color: #fca5a5;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
