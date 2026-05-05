<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { getAdminDocumentChunks, getAdminDocuments } from '../../services/api'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['close'])

const documents = ref([])
const selectedDoc = ref(null)
const chunks = ref([])
const isLoading = ref(false)
const error = ref('')
const currentPage = ref(1)
const totalPages = ref(1)
const pageSize = 20

// Stats
const stats = computed(() => {
  if (!chunks.value.length) return null

  const sizes = chunks.value.map(c => c.text?.length || 0)
  const totalSize = sizes.reduce((a, b) => a + b, 0)
  const avgSize = Math.round(totalSize / sizes.length)
  const minSize = Math.min(...sizes)
  const maxSize = Math.max(...sizes)

  return {
    count: chunks.value.length,
    totalSize,
    avgSize,
    minSize,
    maxSize
  }
})

// Fetch documents list
const fetchDocuments = async () => {
  try {
    const response = await getAdminDocuments()
    documents.value = response.documents || []
  } catch (err) {
    console.error('Failed to fetch documents:', err)
    error.value = 'Failed to load documents'
  }
}

// Fetch chunks for selected document
const fetchChunks = async () => {
  if (!selectedDoc.value) return

  isLoading.value = true
  error.value = ''

  try {
    const docId = selectedDoc.value.name || selectedDoc.value.filename
    const response = await getAdminDocumentChunks(docId, currentPage.value, pageSize)
    chunks.value = response.chunks || []
    totalPages.value = response.total_pages || 1
  } catch (err) {
    console.error('Failed to fetch chunks:', err)
    error.value = 'Failed to load chunks'
    chunks.value = []
  } finally {
    isLoading.value = false
  }
}

// Watch document selection
watch(selectedDoc, () => {
  currentPage.value = 1
  fetchChunks()
})

// Watch page changes
watch(currentPage, () => {
  fetchChunks()
})

// Watch show prop
watch(() => props.show, (newVal) => {
  if (newVal && documents.value.length === 0) {
    fetchDocuments()
  }
})

onMounted(() => {
  if (props.show) {
    fetchDocuments()
  }
})

const getChunkColor = (index) => {
  const colors = [
    'rgba(99, 102, 241, 0.15)',
    'rgba(236, 72, 153, 0.15)',
    'rgba(34, 197, 94, 0.15)',
    'rgba(234, 179, 8, 0.15)',
    'rgba(168, 85, 247, 0.15)',
    'rgba(14, 165, 233, 0.15)',
    'rgba(249, 115, 22, 0.15)',
    'rgba(239, 68, 68, 0.15)'
  ]
  return colors[index % colors.length]
}

const getChunkBorderColor = (index) => {
  const colors = [
    'rgba(99, 102, 241, 0.4)',
    'rgba(236, 72, 153, 0.4)',
    'rgba(34, 197, 94, 0.4)',
    'rgba(234, 179, 8, 0.4)',
    'rgba(168, 85, 247, 0.4)',
    'rgba(14, 165, 233, 0.4)',
    'rgba(249, 115, 22, 0.4)',
    'rgba(239, 68, 68, 0.4)'
  ]
  return colors[index % colors.length]
}

const formatSize = (bytes) => {
  if (bytes < 1024) return `${bytes} chars`
  return `${(bytes / 1024).toFixed(1)}K chars`
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="show" class="chunkviz-overlay" @click.self="emit('close')">
        <div class="chunkviz-modal">
          <!-- Header -->
          <div class="modal-header">
            <div class="header-title">
              <svg class="header-icon" viewBox="0 0 24 24" fill="none">
                <path d="M4 5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5zm10 0a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1V5zM4 15a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-4zm10 0a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1v-4z" stroke="currentColor" stroke-width="1.5"/>
              </svg>
              <h2>Chunk Visualizer</h2>
            </div>
            <button class="close-btn" @click="emit('close')" title="Close" aria-label="Close visualization">
              <svg viewBox="0 0 24 24" fill="none">
                <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          <!-- Content -->
          <div class="modal-content">
            <!-- Document Selector -->
            <div class="section doc-selector">
              <label class="section-label">Select Document</label>
              <select v-model="selectedDoc" class="doc-select">
                <option :value="null" disabled>Choose a document...</option>
                <option 
                  v-for="doc in documents" 
                  :key="doc.name || doc.filename" 
                  :value="doc"
                >
                  {{ doc.name || doc.filename }} ({{ doc.chunk_count || '?' }} chunks)
                </option>
              </select>
            </div>

            <!-- Stats Panel -->
            <div v-if="stats" class="section stats-panel">
              <label class="section-label">Statistics</label>
              <div class="stats-grid">
                <div class="stat-item">
                  <span class="stat-value">{{ stats.count }}</span>
                  <span class="stat-label">Chunks</span>
                </div>
                <div class="stat-item">
                  <span class="stat-value">{{ formatSize(stats.totalSize) }}</span>
                  <span class="stat-label">Total Size</span>
                </div>
                <div class="stat-item">
                  <span class="stat-value">{{ formatSize(stats.avgSize) }}</span>
                  <span class="stat-label">Avg Size</span>
                </div>
                <div class="stat-item">
                  <span class="stat-value">{{ stats.minSize }}-{{ stats.maxSize }}</span>
                  <span class="stat-label">Size Range</span>
                </div>
              </div>
            </div>

            <!-- Chunks Display -->
            <div class="section chunks-section">
              <div class="section-header">
                <label class="section-label">Chunks</label>
                <div v-if="totalPages > 1" class="pagination">
                  <button 
                    class="page-btn" 
                    :disabled="currentPage === 1"
                    @click="currentPage--"
                  >
                    ←
                  </button>
                  <span class="page-info">{{ currentPage }} / {{ totalPages }}</span>
                  <button 
                    class="page-btn" 
                    :disabled="currentPage === totalPages"
                    @click="currentPage++"
                  >
                    →
                  </button>
                </div>
              </div>

              <!-- Loading -->
              <div v-if="isLoading" class="loading-state">
                <div class="spinner"></div>
                <span>Loading chunks...</span>
              </div>

              <!-- Error -->
              <div v-else-if="error" class="error-state">
                <svg viewBox="0 0 24 24" fill="none">
                  <path d="M12 9v4m0 4h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
                <span>{{ error }}</span>
              </div>

              <!-- No selection -->
              <div v-else-if="!selectedDoc" class="empty-state">
                <svg viewBox="0 0 24 24" fill="none">
                  <path d="M9 12h6m-3-3v6m-7 4h14a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2z" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
                <span>Select a document to visualize chunks</span>
              </div>

              <!-- No chunks -->
              <div v-else-if="chunks.length === 0" class="empty-state">
                <svg viewBox="0 0 24 24" fill="none">
                  <path d="M9 12h6m-3-3v6m-7 4h14a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2z" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
                <span>No chunks found for this document</span>
              </div>

              <!-- Chunks list -->
              <div v-else class="chunks-list">
                <div 
                  v-for="(chunk, index) in chunks" 
                  :key="index"
                  class="chunk-item"
                  :style="{ 
                    backgroundColor: getChunkColor(index),
                    borderColor: getChunkBorderColor(index)
                  }"
                >
                  <div class="chunk-header">
                    <span class="chunk-index">#{{ (currentPage - 1) * pageSize + index + 1 }}</span>
                    <span class="chunk-meta">
                      <span v-if="chunk.page !== undefined" class="chunk-page">Page {{ chunk.page }}</span>
                      <span class="chunk-size">{{ chunk.text?.length || 0 }} chars</span>
                    </span>
                  </div>
                  <div class="chunk-text">{{ chunk.text || '(empty)' }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.chunkviz-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.chunkviz-modal {
  background: rgba(15, 23, 42, 0.98);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 16px;
  width: 100%;
  max-width: 900px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 25px 80px rgba(0, 0, 0, 0.5);
}

/* Header */
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-icon {
  width: 24px;
  height: 24px;
  color: var(--accent, #6366f1);
}

.modal-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-main, #e2e8f0);
}

.close-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all 0.2s;
}

.close-btn:hover {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.close-btn svg {
  width: 18px;
  height: 18px;
}

/* Content */
.modal-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

/* Document Selector */
.doc-select {
  width: 100%;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  color: var(--text-main, #e2e8f0);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.doc-select:hover {
  border-color: rgba(99, 102, 241, 0.4);
}

.doc-select:focus {
  outline: none;
  border-color: var(--accent, #6366f1);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
}

.doc-select option {
  background: #1e293b;
  color: #e2e8f0;
}

/* Stats Panel */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.stat-item {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-radius: 10px;
  padding: 14px;
  text-align: center;
}

.stat-value {
  display: block;
  font-size: 20px;
  font-weight: 700;
  color: var(--accent, #6366f1);
  margin-bottom: 4px;
}

.stat-label {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

/* Pagination */
.pagination {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page-btn {
  width: 28px;
  height: 28px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(255, 255, 255, 0.05);
  border-radius: 6px;
  color: var(--text-main, #e2e8f0);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  transition: all 0.2s;
}

.page-btn:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.2);
  border-color: rgba(99, 102, 241, 0.4);
}

.page-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.page-info {
  font-size: 12px;
  color: var(--text-muted);
  min-width: 60px;
  text-align: center;
}

/* States */
.loading-state,
.error-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px 20px;
  color: var(--text-muted);
  text-align: center;
}

.loading-state svg,
.error-state svg,
.empty-state svg {
  width: 40px;
  height: 40px;
  opacity: 0.5;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(99, 102, 241, 0.2);
  border-top-color: var(--accent, #6366f1);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-state {
  color: #fca5a5;
}

.error-state svg {
  color: #ef4444;
  opacity: 1;
}

/* Chunks List */
.chunks-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 400px;
  overflow-y: auto;
  padding-right: 8px;
}

.chunks-list::-webkit-scrollbar {
  width: 6px;
}

.chunks-list::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 3px;
}

.chunks-list::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.2);
  border-radius: 3px;
}

.chunks-list::-webkit-scrollbar-thumb:hover {
  background: rgba(148, 163, 184, 0.3);
}

.chunk-item {
  border: 1px solid;
  border-radius: 10px;
  padding: 14px;
  transition: all 0.2s;
}

.chunk-item:hover {
  transform: translateX(4px);
}

.chunk-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.chunk-index {
  font-size: 13px;
  font-weight: 700;
  color: var(--accent, #6366f1);
}

.chunk-meta {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: var(--text-muted);
}

.chunk-page {
  background: rgba(255, 255, 255, 0.05);
  padding: 2px 8px;
  border-radius: 4px;
}

.chunk-text {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-main, #e2e8f0);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 120px;
  overflow-y: auto;
}

/* Transitions */
.modal-enter-active,
.modal-leave-active {
  transition: all 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .chunkviz-modal,
.modal-leave-to .chunkviz-modal {
  transform: scale(0.95) translateY(20px);
}

/* Responsive */
@media (max-width: 640px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .chunkviz-modal {
    max-height: 90vh;
  }
}
</style>
