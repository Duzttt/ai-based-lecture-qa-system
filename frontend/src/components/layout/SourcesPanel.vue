<script setup>
import { ref, computed, onMounted } from 'vue'
import { useDocumentStore } from '../../stores/documentStore'
import { uploadPDF, getFiles, deleteFile } from '../../services/api'

const documentStore = useDocumentStore()

const sources = ref([])
const showUploadModal = ref(false)
const searchQuery = ref('')
const uploading = ref(false)
const uploadProgress = ref(0)
const uploadError = ref('')
const uploadSuccess = ref(false)
const compareMode = ref(false)
const showSelectionTooltip = ref(false)

// Computed from store
const selectedDocs = computed(() => documentStore.selectedDocIds)
const selectedCount = computed(() => documentStore.selectedCount)
const allSelected = computed(() => documentStore.allSelected)
const hasSelection = computed(() => documentStore.hasSelection)

const loadFiles = async () => {
  try {
    const files = await getFiles()
    sources.value = files.files || []
    documentStore.setAllDocuments(sources.value)
  } catch (err) {
    console.error('Failed to load files:', err)
  }
}

const handleFileUpload = async (event) => {
  const file = event.target.files[0]
  if (!file) return

  if (!file.name.toLowerCase().endsWith('.pdf')) {
    uploadError.value = 'Please upload a PDF file'
    return
  }

  uploading.value = true
  uploadError.value = ''
  uploadProgress.value = 0
  uploadSuccess.value = false

  try {
    await uploadPDF(file, (progress) => {
      uploadProgress.value = progress
    })
    await loadFiles()
    uploadSuccess.value = true
    setTimeout(() => {
      uploadSuccess.value = false
      showUploadModal.value = false
    }, 900)
  } catch (err) {
    uploadError.value = err.response?.data?.error || 'Failed to upload file'
  } finally {
    uploading.value = false
  }
}

const handleDrop = async (event) => {
  event.preventDefault()
  const file = event.dataTransfer.files[0]
  if (!file) return

  if (!file.name.toLowerCase().endsWith('.pdf')) {
    uploadError.value = 'Please upload a PDF file'
    return
  }

  uploading.value = true
  uploadError.value = ''
  uploadProgress.value = 0
  uploadSuccess.value = false

  try {
    await uploadPDF(file, (progress) => {
      uploadProgress.value = progress
    })
    await loadFiles()
    uploadSuccess.value = true
    setTimeout(() => {
      uploadSuccess.value = false
      showUploadModal.value = false
    }, 900)
  } catch (err) {
    uploadError.value = err.response?.data?.error || 'Failed to upload file'
  } finally {
    uploading.value = false
  }
}

const handleDragOver = (event) => {
  event.preventDefault()
}

const removeFile = async (fileId) => {
  const filename = fileId.name || fileId
  if (!confirm(`Delete ${filename}?`)) return

  try {
    await deleteFile(filename)
    await loadFiles()
  } catch (err) {
    uploadError.value = err.response?.data?.error || 'Failed to delete file'
  }
}

const toggleDocSelection = (docName) => {
  documentStore.toggleDocSelection(docName)
}

const isSelected = (docName) => {
  return documentStore.isDocSelected(docName)
}

const toggleSelectAll = () => {
  documentStore.toggleSelectAll()
}

const toggleCompareMode = () => {
  compareMode.value = !compareMode.value
}

const filteredSources = computed(() => {
  if (!searchQuery.value.trim()) {
    return sources.value
  }
  const query = searchQuery.value.toLowerCase()
  return sources.value.filter(source => {
    const name = source.name || source.filename
    return name.toLowerCase().includes(query)
  })
})

onMounted(() => {
  loadFiles()
})
</script>

<template>
  <div class="panel sources-panel">
    <div class="panel-header">
      <div>
        <span class="panel-header-title">Sources</span>
        <span class="panel-header-sub">{{ sources.length }} documents</span>
      </div>
      <div class="panel-header-actions">
        <button
          class="compare-mode-btn"
          :class="{ active: compareMode }"
          @click="toggleCompareMode"
          title="Toggle Compare Mode"
        >
          ⚖
        </button>
        <button class="sources-add" @click="showUploadModal = true">
          <span>+</span> Add
        </button>
      </div>
    </div>
    <div class="sources-body">
      <div class="sources-search">
        <span>🔍</span>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search sources..."
        />
      </div>
      
      <!-- Selection Controls -->
      <div class="selection-controls">
        <button 
          class="btn-select-all"
          @click="toggleSelectAll"
          :disabled="sources.length === 0"
        >
          {{ allSelected ? '✓ Deselect All' : '☐ Select All' }}
        </button>
        <div class="selected-count" :class="{ 'has-selection': hasSelection }">
          <span class="count-icon">📄</span>
          <span class="count-text">{{ selectedCount }} / {{ sources.length }} selected</span>
        </div>
      </div>
      
      <div class="chip-row">
        <span class="chip">📄 PDF</span>
        <span class="chip">📝 Notes</span>
      </div>
      
      <div v-if="sources.length === 0" class="sources-empty">
        <div class="empty-icon">📚</div>
        <div class="empty-text">No sources yet</div>
        <div class="empty-sub">Add your first document to start</div>
      </div>
      
      <div v-else-if="filteredSources.length === 0" class="sources-empty">
        No documents match "{{ searchQuery }}"
      </div>
      
      <div v-else class="sources-list">
        <div
          v-for="source in filteredSources"
          :key="source.id || source.name"
          class="source-item"
          :class="{
            'selected': isSelected(source.name || source.filename),
            'compare-mode': compareMode
          }"
        >
          <input
            type="checkbox"
            :checked="isSelected(source.name || source.filename)"
            @change="toggleDocSelection(source.name || source.filename)"
            class="source-checkbox"
          />
          <span class="source-icon">📄</span>
          <span class="source-name" :title="source.name || source.filename">
            {{ source.name || source.filename }}
          </span>
          <button class="source-remove" @click.stop="removeFile(source.id)">✕</button>
        </div>
      </div>
    </div>

    <!-- Upload Modal -->
    <div v-if="showUploadModal" class="upload-overlay" @click.self="showUploadModal = false">
      <div class="upload-modal" @drop="handleDrop" @dragover="handleDragOver">
        <div class="upload-header">
          <h3>Upload PDF</h3>
          <button class="upload-close" @click="showUploadModal = false">✕</button>
        </div>
        <div class="upload-body">
          <label class="upload-area">
            <input
              type="file"
              accept=".pdf"
              @change="handleFileUpload"
              :disabled="uploading"
              hidden
            />
            <div class="upload-icon">📁</div>
            <div class="upload-text">
              <span class="primary">Click to upload</span> or drag and drop
            </div>
            <div class="upload-hint">PDF files only (max 10MB)</div>
          </label>
          <div v-if="uploading" class="upload-progress">
            <div class="upload-progress-bar" :style="{ width: uploadProgress + '%' }"></div>
            <div class="upload-spinner-wrap">
              <div class="upload-spinner"></div>
              <span class="upload-spinner-text">Uploading, please wait...</span>
            </div>
          </div>
          <div v-else-if="uploadSuccess" class="upload-success">
            <div class="success-icon-wrap">
              <div class="success-ring"></div>
              <div class="success-icon">✔</div>
            </div>
            <div class="success-text-main">Upload complete</div>
            <div class="success-text-sub">Returning to home...</div>
          </div>
          <div v-if="uploadError" class="upload-error">{{ uploadError }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sources-panel {
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
  backdrop-filter: blur(15px) saturate(180%);
  -webkit-backdrop-filter: blur(15px) saturate(180%);
  box-shadow:
    0 15px 30px -15px rgba(0, 0, 0, 0.6),
    inset 0 1px 1px rgba(255, 255, 255, 0.1),
    inset 0 -2px 2px rgba(0, 0, 0, 0.2);
  transition: all 0.3s ease;
  position: relative;
}

.sources-panel:hover {
  border-color: rgba(255, 255, 255, 0.15);
  box-shadow:
    0 20px 40px -15px rgba(0, 0, 0, 0.7),
    inset 0 1px 2px rgba(255, 255, 255, 0.15);
}

.panel-header {
  padding: 10px 12px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.9);
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
}

.panel-header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.compare-mode-btn {
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
  font-size: 16px;
  transition: all 0.2s;
}

.compare-mode-btn:hover {
  background: rgba(99, 102, 241, 0.2);
  border-color: var(--accent);
  color: white;
}

.compare-mode-btn.active {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.5), rgba(168, 85, 247, 0.5));
  border-color: var(--accent);
  color: white;
  box-shadow: 0 0 15px rgba(99, 102, 241, 0.4);
}

.panel-header-title {
  font-weight: 600;
  display: block;
}

.panel-header-sub {
  font-size: 11px;
  color: var(--text-muted);
}

.sources-add {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px dashed rgba(75, 85, 99, 0.9);
  font-size: 11px;
  color: var(--text-main);
  cursor: pointer;
  background: transparent;
  transition: all 0.2s;
}

.sources-add:hover {
  border-color: var(--accent);
  background: rgba(99, 102, 241, 0.1);
}

.sources-body {
  padding: calc(var(--spacing-unit) + 2px);
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 12px;
}

.sources-search {
  display: flex;
  gap: 6px;
  align-items: center;
  border-radius: 999px;
  padding: 6px 10px;
  background: #020617;
  border: 1px solid rgba(55, 65, 81, 0.8);
}

.sources-search input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-main);
  font-size: 12px;
}

/* Selection Controls */
.selection-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  background: rgba(2, 6, 23, 0.6);
  border-radius: 8px;
  border: 1px solid rgba(55, 65, 81, 0.8);
}

.btn-select-all {
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid rgba(99, 102, 241, 0.4);
  background: rgba(99, 102, 241, 0.1);
  color: var(--accent);
  font-size: 10px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.btn-select-all:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.2);
  border-color: var(--accent);
}

.btn-select-all:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.selected-count {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
  font-size: 10px;
  color: var(--text-muted);
  transition: all 0.2s;
}

.selected-count.has-selection {
  background: rgba(99, 102, 241, 0.15);
  border: 1px solid rgba(99, 102, 241, 0.3);
  color: var(--accent);
}

.count-icon {
  font-size: 12px;
}

.count-text {
  font-weight: 600;
}

.chip-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.chip {
  padding: 3px 8px;
  border-radius: 999px;
  background: var(--bg-chip);
  border: 1px solid rgba(55, 65, 81, 0.9);
  font-size: 11px;
  color: var(--text-muted);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.sources-empty {
  margin-top: var(--spacing-unit);
  padding: 20px 10px;
  border-radius: 10px;
  border: 1px dashed rgba(55, 65, 81, 0.9);
  background: rgba(15, 23, 42, 0.4);
  color: var(--text-muted);
  font-size: 11px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.empty-icon {
  font-size: 24px;
  opacity: 0.5;
}

.empty-text {
  font-size: 12px;
  color: var(--text-main);
  font-weight: 600;
}

.empty-sub {
  font-size: 10px;
}

.sources-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 8px;
  max-height: 300px;
  overflow-y: auto;
}

.source-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  cursor: pointer;
  transition: all 0.2s;
}

.source-item:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(99, 102, 241, 0.3);
}

.source-item.compare-mode {
  cursor: pointer;
}

.source-item.selected {
  background: rgba(99, 102, 241, 0.2);
  border-color: var(--accent);
  box-shadow: 0 0 0 1px rgba(99, 102, 241, 0.2);
}

.source-item.selected .source-name {
  color: white;
  font-weight: 600;
}

.source-checkbox {
  width: 16px;
  height: 16px;
  cursor: pointer;
  accent-color: var(--accent);
  flex-shrink: 0;
}

.source-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.source-name {
  font-size: 12px;
  color: var(--text-main);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.source-remove {
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
  font-size: 12px;
  transition: all 0.2s;
  flex-shrink: 0;
}

.source-remove:hover {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

/* Upload Modal */
.upload-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  animation: fadeIn 0.2s ease;
}

.upload-modal {
  width: 90%;
  max-width: 400px;
  background: rgba(15, 23, 42, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  box-shadow: 0 30px 60px -20px rgba(0, 0, 0, 0.8);
  animation: slideUp 0.3s ease;
  overflow: hidden;
}

.upload-header {
  padding: 16px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.upload-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-main);
}

.upload-close {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.upload-close:hover {
  background: rgba(255, 255, 255, 0.1);
  color: white;
  transform: rotate(90deg);
}

.upload-body {
  padding: 20px;
}

.upload-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 30px 20px;
  border: 2px dashed rgba(255, 255, 255, 0.15);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.02);
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
}

.upload-area:hover {
  border-color: var(--accent);
  background: rgba(99, 102, 241, 0.05);
}

.upload-area.drag-over {
  border-color: var(--accent);
  background: rgba(99, 102, 241, 0.1);
}

.upload-icon {
  font-size: 40px;
  margin-bottom: 12px;
}

.upload-text {
  font-size: 14px;
  margin-bottom: 6px;
  color: var(--text-main);
}

.upload-text .primary {
  color: var(--accent);
  font-weight: 500;
}

.upload-hint {
  font-size: 11px;
  color: var(--text-muted);
}

.upload-progress {
  margin-top: 12px;
  height: 4px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
  overflow: hidden;
  position: relative;
}

.upload-progress-bar {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), #a855f7);
  transition: width 0.3s;
}

.upload-spinner-wrap {
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--text-muted);
}

.upload-spinner {
  width: 16px;
  height: 16px;
  border-radius: 999px;
  border: 2px solid rgba(148, 163, 184, 0.4);
  border-top-color: var(--accent);
  animation: spin 0.8s linear infinite;
}

.upload-success {
  margin-top: 14px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(34, 197, 94, 0.5);
  background: radial-gradient(circle at 0 0, rgba(34, 197, 94, 0.35), transparent),
    rgba(22, 163, 74, 0.15);
  text-align: center;
}

.success-icon-wrap {
  position: relative;
  width: 34px;
  height: 34px;
  margin: 0 auto 6px;
}

.success-ring {
  position: absolute;
  inset: 0;
  border-radius: 999px;
  border: 2px solid rgba(74, 222, 128, 0.4);
  border-top-color: rgba(190, 242, 100, 0.9);
  animation: spin 0.9s ease-out;
}

.success-icon {
  position: relative;
  width: 100%;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(135deg, #22c55e, #a3e635);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  color: #022c22;
  box-shadow:
    0 8px 18px rgba(22, 163, 74, 0.5),
    inset 0 1px 2px rgba(255, 255, 255, 0.7);
}

.success-text-main {
  font-size: 12px;
  font-weight: 600;
  color: #bbf7d0;
}

.success-text-sub {
  margin-top: 2px;
  font-size: 11px;
  color: var(--text-muted);
}

.upload-error {
  margin-top: 12px;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #fca5a5;
  font-size: 12px;
  text-align: center;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
