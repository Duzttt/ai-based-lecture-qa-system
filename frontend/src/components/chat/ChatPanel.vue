<script setup>
import { ref, computed } from 'vue'
import { useDocumentStore } from '../../stores/documentStore'
import ChatHeader from './ChatHeader.vue'
import ChatMessageList from './ChatMessageList.vue'
import ChatInput from './ChatInput.vue'
import RetrievalChunks from './RetrievalChunks.vue'
import PdfViewer from '../documents/PdfViewer.vue'
import BidirectionalCitations from '../shared/BidirectionalCitations.vue'
import QuestionSuggestions from './QuestionSuggestions.vue'

const documentStore = useDocumentStore()

const messages = ref([])
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

// Bidirectional citations index
const bidirectionalIndex = ref({})

// Computed
const selectedSources = computed(() => documentStore.selectedDocIds)
const selectedCount = computed(() => documentStore.selectedCount)
const selectedDocuments = computed(() => documentStore.selectedDocuments)
const hasSelection = computed(() => documentStore.hasSelection)

const sendMessage = async (questionText) => {
  if (!questionText.trim()) return

  const userQuestion = questionText
  const userMsgIndex = messages.value.length

  messages.value.push({
    role: 'user',
    content: userQuestion,
    id: `msg_user_${Date.now()}_${userMsgIndex}`,
  })
  isLoading.value = true
  isRetrieving.value = true
  error.value = ''
  lastRetrievedChunks.value = []
  let timeoutId = null

  try {
    const payload = { query: userQuestion }

    if (selectedSources.value && selectedSources.value.length > 0) {
      payload.sources = selectedSources.value
    }

    const controller = new AbortController()
    timeoutId = setTimeout(() => controller.abort(), 30000)
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || errorData.error || 'Failed to get response')
    }

    const data = await response.json()

    const sentences = data.sentences || []
    const sources = data.sources || {}
    const chunks = data.retrieved_chunks || []
    const reasoning = data.reasoning || null
    const answerText = (data.answer || sentences.map(s => s.text).join(' ') || 'No answer received.').toString()

    messages.value.push({
      role: 'assistant',
      content: answerText,
      reasoning: reasoning,
      sentences: sentences,
      sources: sources,
      chunks: chunks,
      id: `msg_${Date.now()}`
    })

    registerCitations(messages.value[messages.value.length - 1].id, userQuestion, answerText, chunks)
    lastRetrievedChunks.value = chunks
  } catch (err) {
    if (err.name === 'AbortError') {
      error.value = 'Request timed out. Please try again with a shorter question.'
    } else {
      error.value = err.message
    }
  } finally {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
    isLoading.value = false
    isRetrieving.value = false
  }
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
      answer: answer.substring(0, 150) + (answer.length > 150 ? '…' : ''),
      timestamp: new Date().toLocaleTimeString(),
      source: chunk.source,
      page: chunk.page,
      text: chunk.text
    })
  })
}

const handleChunkClick = (chunk) => {
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
      element.offsetHeight
      element.style.animation = 'highlightMessage 1s ease'
    }
  }, 100)
}

const handleSuggestionSelect = (questionText) => {
  sendMessage(questionText)
}
</script>

<template>
  <div class="panel chat-panel">
    <ChatHeader
      :has-selection="hasSelection"
      :selected-count="selectedCount"
      :selected-documents="selectedDocuments"
    />

    <ChatMessageList
      :messages="messages"
      :is-loading="isLoading"
      :is-retrieving="isRetrieving"
      :has-selection="hasSelection"
      :selected-documents="selectedDocuments"
      @chunk-click="handleChunkClick"
      @chunk-rightclick="handleChunkRightClick"
      @suggestion-click="handleSuggestionSelect"
    />

    <div v-if="messages.length > 0" class="chat-suggestions-wrap">
      <QuestionSuggestions
        :selected-documents="selectedDocuments"
        :disabled="isLoading"
        @question-select="handleSuggestionSelect"
      />
    </div>

    <ChatInput
      :is-loading="isLoading"
      @send="sendMessage"
    />

    <div v-if="error" class="chat-error" role="alert">{{ error }}</div>

    <PdfViewer
      :show="showPdfViewer"
      :pdf-url="currentPdfUrl"
      :target-page="currentPdfPage"
      :highlight-text="currentHighlightText"
      @close="closePdfViewer"
    />

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
  0% { background: rgba(129, 140, 248, 0.2); }
  100% { background: transparent; }
}

.chat-panel {
  position: relative;
  background: var(--surface);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
  min-height: 0;
  height: 100%;
}

.chat-suggestions-wrap {
  padding: 0 16px 4px;
}

.chat-error {
  margin: 0 16px 4px;
  min-height: 1.2em;
  font-size: 12px;
  color: #fca5a5;
}
</style>
