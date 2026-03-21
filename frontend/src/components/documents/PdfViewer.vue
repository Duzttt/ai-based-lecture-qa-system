<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false,
  },
  pdfUrl: {
    type: String,
    default: '',
  },
  targetPage: {
    type: Number,
    default: 1,
  },
  highlightText: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['close', 'page-change'])

const currentPage = ref(1)
const totalPages = ref(0)
const pdfDoc = ref(null)
const canvas = ref(null)
const isLoading = ref(false)
const error = ref('')
const scale = ref(1.5)

let pdfjsLib = null

onMounted(async () => {
  // Load PDF.js dynamically
  if (window.pdfjsLib) {
    pdfjsLib = window.pdfjsLib
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js'
  }
})

onUnmounted(() => {
  if (pdfDoc.value) {
    pdfDoc.value.destroy()
    pdfDoc.value = null
  }
})

const loadPdf = async () => {
  if (!props.pdfUrl || !pdfjsLib) return

  isLoading.value = true
  error.value = ''

  try {
    const loadingTask = pdfjsLib.getDocument({
      url: props.pdfUrl,
      useWorkerFetch: false,
    })
    pdfDoc.value = await loadingTask.promise
    totalPages.value = pdfDoc.value.numPages
    currentPage.value = props.targetPage || 1
    await renderPage(currentPage.value)
  } catch (err) {
    console.error('Failed to load PDF:', err)
    error.value = 'Failed to load PDF: ' + err.message
  } finally {
    isLoading.value = false
  }
}

const renderPage = async (pageNum) => {
  if (!pdfDoc.value || !canvas.value) return

  try {
    const page = await pdfDoc.value.getPage(pageNum)
    const viewport = page.getViewport({ scale: scale.value })

    const ctx = canvas.value.getContext('2d')
    canvas.value.height = viewport.height
    canvas.value.width = viewport.width

    await page.render({
      canvasContext: ctx,
      viewport: viewport,
    }).promise

    // Highlight text if provided
    if (props.highlightText) {
      await highlightTextOnPage(page, props.highlightText)
    }

    emit('page-change', pageNum)
  } catch (err) {
    console.error('Failed to render page:', err)
    error.value = 'Failed to render page: ' + err.message
  }
}

const highlightTextOnPage = async (page, text) => {
  // Get text content and find matches
  const textContent = await page.getTextContent()
  const viewport = page.getViewport({ scale: scale.value })

  // Simple text search - find matching text items
  const textItems = textContent.items.filter(item => item.str)

  for (const item of textItems) {
    if (item.str.toLowerCase().includes(text.toLowerCase())) {
      // Get position and draw highlight
      const transform = item.transform
      const x = transform[4]
      const y = viewport.height - transform[5]
      const width = item.width * scale.value
      const height = item.height * scale.value

      // Draw highlight overlay
      const ctx = canvas.value.getContext('2d')
      ctx.fillStyle = 'rgba(255, 255, 0, 0.4)'
      ctx.fillRect(x * scale.value, y - height * scale.value, width, height)
    }
  }
}

const previousPage = () => {
  if (currentPage.value > 1) {
    currentPage.value--
    renderPage(currentPage.value)
  }
}

const nextPage = () => {
  if (currentPage.value < totalPages.value) {
    currentPage.value++
    renderPage(currentPage.value)
  }
}

const zoomIn = () => {
  scale.value = Math.min(scale.value + 0.25, 3)
  renderPage(currentPage.value)
}

const zoomOut = () => {
  scale.value = Math.max(scale.value - 0.25, 0.5)
  renderPage(currentPage.value)
}

// Watch for PDF URL changes
import { watch } from 'vue'
watch(() => props.pdfUrl, (newUrl) => {
  if (newUrl) {
    loadPdf()
  }
}, { immediate: true })

watch(() => props.show, (newShow) => {
  if (newShow && props.pdfUrl) {
    loadPdf()
  }
})
</script>

<template>
  <div v-if="show" class="pdf-viewer-panel" :class="{ visible: show }">
    <div class="pdf-viewer-header">
      <div class="pdf-viewer-title">
        <span>📄</span>
        <span>{{ pdfUrl ? pdfUrl.split('/').pop() : 'PDF Viewer' }}</span>
      </div>
      <div class="pdf-viewer-actions">
        <button class="pdf-viewer-btn" @click="zoomOut" title="Zoom Out">−</button>
        <button class="pdf-viewer-btn" @click="zoomIn" title="Zoom In">+</button>
        <button class="pdf-viewer-btn" @click="$emit('close')" title="Close">✕</button>
      </div>
    </div>

    <div class="pdf-viewer-nav">
      <button class="pdf-viewer-nav-btn" @click="previousPage" :disabled="currentPage <= 1">◀</button>
      <div class="pdf-viewer-page-info">
        Page <span class="current-page">{{ currentPage }}</span> of {{ totalPages || '--' }}
      </div>
      <button class="pdf-viewer-nav-btn" @click="nextPage" :disabled="currentPage >= totalPages">▶</button>
    </div>

    <div class="pdf-viewer-body" id="pdfViewerBody">
      <div v-if="isLoading" class="pdf-loading">
        <div class="pdf-loading-spinner"></div>
        <span>Loading PDF...</span>
      </div>

      <div v-else-if="error" class="pdf-error">
        <span>⚠️</span>
        <span>{{ error }}</span>
      </div>

      <div v-else class="pdf-canvas-container">
        <canvas ref="canvas" id="pdfCanvas"></canvas>
      </div>
    </div>
  </div>
</template>

<style scoped>
.pdf-viewer-panel {
  position: fixed;
  top: 80px;
  right: 20px;
  width: 450px;
  height: calc(100vh - 100px);
  background: rgba(15, 23, 42, 0.98);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6);
  z-index: 4000;
  overflow: hidden;
  display: none;
  flex-direction: column;
}

.pdf-viewer-panel.visible {
  display: flex;
}

.pdf-viewer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: rgba(99, 102, 241, 0.15);
  border-bottom: 1px solid rgba(99, 102, 241, 0.2);
  flex-shrink: 0;
}

.pdf-viewer-title {
  font-size: 13px;
  font-weight: 600;
  color: white;
  display: flex;
  align-items: center;
  gap: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pdf-viewer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pdf-viewer-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  transition: all 0.2s;
}

.pdf-viewer-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: white;
}

.pdf-viewer-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: rgba(0, 0, 0, 0.2);
  border-bottom: 1px solid rgba(55, 65, 81, 0.5);
  flex-shrink: 0;
}

.pdf-viewer-nav-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-main);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  transition: all 0.2s;
}

.pdf-viewer-nav-btn:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.3);
  border-color: var(--accent);
}

.pdf-viewer-nav-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.pdf-viewer-page-info {
  font-size: 12px;
  color: var(--text-muted);
}

.pdf-viewer-page-info .current-page {
  color: var(--accent);
  font-weight: 600;
}

.pdf-viewer-body {
  flex: 1;
  overflow: auto;
  background: #1a1a1a;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.pdf-canvas-container {
  position: relative;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
  border-radius: 4px;
  overflow: hidden;
  max-width: 100%;
}

#pdfCanvas {
  display: block;
  max-width: 100%;
  height: auto;
}

.pdf-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--text-muted);
  gap: 12px;
}

.pdf-loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(99, 102, 241, 0.2);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.pdf-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #fca5a5;
  gap: 12px;
  text-align: center;
  font-size: 12px;
}
</style>
