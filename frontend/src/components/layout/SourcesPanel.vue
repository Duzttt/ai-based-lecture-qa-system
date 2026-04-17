<script setup>
import { ref, computed, onMounted } from 'vue'
import { useDocumentStore } from '../../stores/documentStore'
import { uploadPDF, getFiles, deleteFile } from '../../services/api'

const documentStore = useDocumentStore()

const emit = defineEmits(['selection-change', 'toggle-compare'])

const sources = ref([])
const showUploadModal = ref(false)
const searchQuery = ref('')
const uploading = ref(false)
const uploadProgress = ref(0)
const uploadError = ref('')
const uploadSuccess = ref(false)
const uploadResults = ref([])
const compareMode = ref(false)
const deletingFiles = ref(new Set())

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

const uploadFile = async (file) => {
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    return { filename: file.name, success: false, error: 'Not a PDF file' }
  }
  try {
    await uploadPDF(file, null)
    return { filename: file.name, success: true }
  } catch (err) {
    return { filename: file.name, success: false, error: err.response?.data?.error || 'Upload failed' }
  }
}

const handleFileUpload = async (event) => {
  const files = Array.from(event.target.files)
  if (files.length === 0) return

  uploading.value = true
  uploadError.value = ''
  uploadProgress.value = 0
  uploadSuccess.value = false
  uploadResults.value = []

  for (let i = 0; i < files.length; i++) {
    const result = await uploadFile(files[i])
    uploadResults.value.push(result)
    uploadProgress.value = Math.round(((i + 1) / files.length) * 100)
  }

  const successCount = uploadResults.value.filter(r => r.success).length
  const failCount = uploadResults.value.length - successCount

  if (failCount > 0) {
    uploadError.value = `${failCount} of ${uploadResults.value.length} file${uploadResults.value.length > 1 ? 's' : ''} failed to upload`
  } else {
    uploadSuccess.value = true
  }

  await loadFiles()

  setTimeout(() => {
    uploadSuccess.value = false
    uploadError.value = ''
    uploadResults.value = []
    showUploadModal.value = false
  }, 1500)
}

const handleDrop = async (event) => {
  event.preventDefault()
  const files = Array.from(event.dataTransfer.files)
  if (files.length === 0) return

  uploading.value = true
  uploadError.value = ''
  uploadProgress.value = 0
  uploadSuccess.value = false
  uploadResults.value = []

  for (let i = 0; i < files.length; i++) {
    const result = await uploadFile(files[i])
    uploadResults.value.push(result)
    uploadProgress.value = Math.round(((i + 1) / files.length) * 100)
  }

  const successCount = uploadResults.value.filter(r => r.success).length
  const failCount = uploadResults.value.length - successCount

  if (failCount > 0) {
    uploadError.value = `${failCount} of ${uploadResults.value.length} file${uploadResults.value.length > 1 ? 's' : ''} failed to upload`
  } else {
    uploadSuccess.value = true
  }

  await loadFiles()

  setTimeout(() => {
    uploadSuccess.value = false
    uploadError.value = ''
    uploadResults.value = []
    showUploadModal.value = false
  }, 1500)
}

const handleDragOver = (event) => { event.preventDefault() }

const removeFile = async (filename) => {
  if (!filename) return

  const sourceKey = filename
  if (deletingFiles.value.has(sourceKey)) return

  // Mark as deleting
  deletingFiles.value.add(sourceKey)

  // Deselect if selected
  if (documentStore.isDocSelected(filename)) {
    documentStore.deselectDoc(filename)
  }

  try {
    await deleteFile(filename)
    // Remove from sources after successful delete
    sources.value = sources.value.filter(s => (s.name || s.filename) !== filename)
  } catch (err) {
    uploadError.value = err.response?.data?.error || 'Failed to delete file'
  } finally {
    deletingFiles.value.delete(sourceKey)
  }
}

const toggleDocSelection = (docName) => {
  documentStore.toggleDocSelection(docName)
}

const onSourceRowKeydown = (event, docName) => {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    toggleDocSelection(docName)
  }
}

const isSelected = (docName) => documentStore.isDocSelected(docName)
const toggleSelectAll = () => { documentStore.toggleSelectAll() }
const toggleCompareMode = () => { compareMode.value = !compareMode.value }

const filteredSources = computed(() => {
  if (!searchQuery.value.trim()) return sources.value
  const query = searchQuery.value.toLowerCase()
  return sources.value.filter(source => {
    const name = source.name || source.filename
    return name.toLowerCase().includes(query)
  })
})

onMounted(() => { loadFiles() })
</script>

<template>
  <div class="panel sources-panel">
    <div class="panel-header">
      <div class="header-title-group">
        <h2 class="panel-title">Lecture Vault</h2>
        <span class="panel-subtitle">Academic Year 2024</span>
      </div>
      <button type="button" class="select-all-btn" @click="toggleSelectAll" :disabled="sources.length === 0">
        {{ allSelected ? 'Deselect All' : 'Select All' }}
      </button>
    </div>

    <div class="panel-body">
      <div class="sources-search">
        <svg class="search-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search sources…"
          aria-label="Search sources"
        />
      </div>

      <div v-if="sources.length === 0" class="sources-empty">
        <svg class="empty-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M18 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM6 4h5v8l-2.5-1.5L6 12V4z"/></svg>
        <div class="empty-text">No sources yet</div>
        <div class="empty-sub">Add your first document to start</div>
      </div>

      <div v-else-if="filteredSources.length === 0" class="sources-empty">
        No documents match "{{ searchQuery }}"
      </div>

      <div v-else class="sources-list">
        <TransitionGroup name="source-list">
          <div
            v-for="source in filteredSources"
            :key="source.name"
            class="source-item"
            role="button"
            tabindex="0"
            :aria-pressed="isSelected(source.name || source.filename)"
            :aria-label="`Select ${source.name || source.filename}`"
            :class="{
              'selected': isSelected(source.name || source.filename),
              'compare-mode': compareMode,
              'deleting': deletingFiles.has(source.name || source.filename)
            }"
            @click="toggleDocSelection(source.name || source.filename)"
            @keydown="onSourceRowKeydown($event, source.name || source.filename)"
          >
            <svg class="source-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/></svg>
            <span class="source-name" :title="source.name || source.filename">
              {{ source.name || source.filename }}
            </span>
            <button type="button" class="source-remove" @click.stop="removeFile(source.name)" :class="{ deleting: deletingFiles.has(source.name || source.filename) }" :aria-label="`Remove ${source.name || source.filename}`">
              <svg v-if="deletingFiles.has(source.name || source.filename)" class="deleting-spinner" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" fill="none" stroke-dasharray="31.4 31.4" stroke-linecap="round"/></svg>
              <svg v-else viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
            </button>
          </div>
        </TransitionGroup>
      </div>
    </div>

    <div class="panel-footer">
      <button type="button" class="footer-btn" @click="showUploadModal = true">
        <svg class="footer-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM14 13v4h-4v-4H7l5-5 5 5h-3z"/></svg>
        Manage Sources
      </button>
    </div>

    <!-- Upload Modal -->
    <div
      v-if="showUploadModal"
      class="upload-overlay"
      role="presentation"
      @click.self="showUploadModal = false"
    >
      <div class="upload-modal" @drop="handleDrop" @dragover="handleDragOver">
        <div class="upload-header">
          <h3>Upload PDF</h3>
          <button type="button" class="upload-close" @click="showUploadModal = false" aria-label="Close upload dialog">
            <svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
          </button>
        </div>
        <div class="upload-body">
          <label class="upload-area">
            <input type="file" accept=".pdf" multiple @change="handleFileUpload" :disabled="uploading" hidden />
            <svg class="upload-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM14 13v4h-4v-4H7l5-5 5 5h-3z"/></svg>
            <div class="upload-text">
              <span class="primary">Click to upload</span> or drag and drop
            </div>
            <div class="upload-hint">PDF files only, multiple files supported (max 10MB each)</div>
          </label>
          <div v-if="uploading" class="upload-progress">
            <div class="upload-progress-bar" :style="{ width: uploadProgress + '%' }"></div>
            <div class="upload-spinner-wrap">
              <div class="upload-spinner"></div>
              <span>Uploading {{ uploadResults.length }} file{{ uploadResults.length !== 1 ? 's' : '' }}…</span>
            </div>
          </div>
          <div v-else-if="uploadSuccess" class="upload-success">
            <svg class="success-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
            <span>{{ uploadResults.length }} file{{ uploadResults.length !== 1 ? 's' : '' }} uploaded</span>
          </div>
          <div v-if="uploadError" class="upload-error">{{ uploadError }}</div>
          <div v-if="uploadResults.length > 0 && !uploading" class="upload-results-list">
            <div v-for="(result, idx) in uploadResults" :key="idx" :class="['upload-result-item', result.success ? 'success' : 'error']">
              <svg v-if="result.success" class="result-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
              <svg v-else class="result-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
              <span class="result-filename">{{ result.filename }}</span>
              <span v-if="!result.success" class="result-error">{{ result.error }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sources-panel {
  background: var(--surface-container-low);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.panel-header {
  padding: 16px 16px 12px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.header-title-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.panel-title {
  font-family: var(--font-headline);
  font-size: 16px;
  font-weight: 700;
  color: var(--on-surface);
  margin: 0;
  letter-spacing: -0.01em;
}

.panel-subtitle {
  font-size: 12px;
  color: var(--on-surface-variant);
}

.select-all-btn {
  padding: 5px 12px;
  border-radius: 6px;
  border: 1px solid var(--outline-variant);
  background: transparent;
  color: var(--primary);
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s, border-color 0.2s;
}

.select-all-btn:hover:not(:disabled) {
  background: rgba(129, 140, 248, 0.1);
  border-color: var(--primary-container);
}

.select-all-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.select-all-btn:focus-visible {
  outline: 2px solid var(--primary);
  outline-offset: 2px;
}

.panel-body {
  flex: 1;
  padding: 0 12px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sources-search {
  display: flex;
  gap: 8px;
  align-items: center;
  border-radius: 8px;
  padding: 8px 12px;
  background: var(--surface-container);
  border: 1px solid rgba(69, 70, 83, 0.15);
  transition: border-color 0.2s;
}

.sources-search:focus-within {
  border-color: var(--primary-container);
}

.search-icon {
  width: 16px;
  height: 16px;
  color: var(--on-surface-variant);
  flex-shrink: 0;
}

.sources-search input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  color: var(--on-surface);
  font-family: var(--font-body);
  font-size: 13px;
}

.sources-search input:focus {
  outline: none;
}

.sources-search input:focus-visible {
  outline: 2px solid var(--primary-container);
  outline-offset: 2px;
  border-radius: 4px;
}

.sources-search input::placeholder {
  color: var(--on-surface-variant);
  opacity: 0.6;
}

.sources-empty {
  margin-top: 16px;
  padding: 24px 16px;
  border-radius: 10px;
  background: var(--surface-container);
  color: var(--on-surface-variant);
  font-size: 12px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.empty-icon {
  width: 32px;
  height: 32px;
  color: var(--outline);
  opacity: 0.5;
}

.empty-text {
  font-size: 13px;
  color: var(--on-surface);
  font-weight: 600;
  font-family: var(--font-headline);
}

.empty-sub {
  font-size: 11px;
  color: var(--on-surface-variant);
  opacity: 0.7;
}

.sources-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.source-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  transition: background-color 0.15s;
}

.source-item:focus {
  outline: none;
}

.source-item:focus-visible {
  outline: 2px solid var(--primary-container);
  outline-offset: 2px;
}

.source-item:hover {
  background: var(--surface-container);
}

.source-item.selected {
  background: rgba(129, 140, 248, 0.12);
}

.source-item.selected .source-name {
  color: var(--primary);
  font-weight: 500;
}

.source-icon {
  width: 20px;
  height: 20px;
  color: var(--on-surface-variant);
  flex-shrink: 0;
  opacity: 0.7;
}

.source-item.selected .source-icon {
  color: var(--primary-container);
  opacity: 1;
}

.source-name {
  font-size: 13px;
  color: var(--on-surface);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.source-item.deleting {
  opacity: 0.4;
  pointer-events: none;
}

.source-list-move,
.source-list-enter-active,
.source-list-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}

.source-list-leave-active {
  position: absolute;
}

.source-list-leave-to {
  opacity: 0;
  transform: translateX(30px);
}

.source-list-enter-from {
  opacity: 0;
  transform: translateX(-30px);
}

.source-list-move {
  transition: transform 0.2s;
}

.source-remove {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--on-surface-variant);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.15s, background-color 0.15s, color 0.15s;
  flex-shrink: 0;
}

.source-remove svg {
  width: 16px;
  height: 16px;
}

.source-item:hover .source-remove {
  opacity: 0.6;
}

.source-remove:hover {
  opacity: 1 !important;
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.source-remove:focus-visible {
  opacity: 1 !important;
  outline: 2px solid #ef4444;
  outline-offset: 1px;
}

.source-remove.deleting {
  opacity: 1 !important;
  pointer-events: none;
}

.deleting-spinner {
  width: 16px;
  height: 16px;
  animation: spin 0.8s linear infinite;
}

.panel-footer {
  padding: 12px;
  display: flex;
  gap: 8px;
  align-items: center;
  border-top: 1px solid rgba(69, 70, 83, 0.1);
  margin-top: auto;
}

.footer-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 8px;
  border: none;
  background: var(--surface-container);
  color: var(--on-surface-variant);
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s, color 0.2s;
}

.footer-btn:hover {
  background: var(--surface-container-high);
  color: var(--on-surface);
}

.footer-btn:focus-visible {
  outline: 2px solid var(--primary);
  outline-offset: 2px;
}

.footer-icon {
  width: 16px;
  height: 16px;
}

/* Upload Modal */
.upload-overlay {
  position: absolute;
  inset: 0;
  background: rgba(6, 14, 32, 0.8);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  animation: fadeIn 0.2s ease;
  overscroll-behavior: contain;
}

.upload-modal {
  width: 90%;
  max-width: 380px;
  background: var(--surface-container);
  border-radius: 14px;
  box-shadow: 0 24px 48px rgba(6, 14, 32, 0.6);
  animation: slideUp 0.3s ease;
  overflow: hidden;
  overscroll-behavior: contain;
}

.upload-header {
  padding: 16px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.upload-header h3 {
  margin: 0;
  font-family: var(--font-headline);
  font-size: 16px;
  font-weight: 600;
  color: var(--on-surface);
}

.upload-close {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--on-surface-variant);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s, color 0.2s;
}

.upload-close svg {
  width: 18px;
  height: 18px;
}

.upload-close:hover {
  background: rgba(255, 255, 255, 0.06);
  color: var(--on-surface);
}

.upload-close:focus-visible {
  outline: 2px solid var(--primary-container);
  outline-offset: 2px;
}

.upload-body {
  padding: 0 20px 20px;
}

.upload-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32px 20px;
  border: 2px dashed rgba(69, 70, 83, 0.3);
  border-radius: 10px;
  background: var(--surface-container-lowest);
  cursor: pointer;
  transition: border-color 0.2s, background-color 0.2s;
  text-align: center;
}

.upload-area:hover {
  border-color: var(--primary-container);
  background: rgba(129, 140, 248, 0.04);
}

.upload-icon {
  width: 40px;
  height: 40px;
  margin-bottom: 12px;
  color: var(--primary-container);
}

.upload-text {
  font-size: 13px;
  margin-bottom: 6px;
  color: var(--on-surface);
}

.upload-text .primary {
  color: var(--primary);
  font-weight: 500;
}

.upload-hint {
  font-size: 11px;
  color: var(--on-surface-variant);
}

.upload-progress {
  margin-top: 12px;
}

.upload-progress-bar {
  height: 3px;
  background: var(--surface-container-highest);
  border-radius: 2px;
  overflow: hidden;
}

.upload-progress-bar {
  height: 100%;
  background: linear-gradient(90deg, var(--primary-container), #6366f1);
  transition: width 0.3s;
}

.upload-spinner-wrap {
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--on-surface-variant);
}

.upload-spinner {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid var(--outline-variant);
  border-top-color: var(--primary-container);
  animation: spin 0.8s linear infinite;
}

.upload-success {
  margin-top: 14px;
  padding: 12px;
  border-radius: 8px;
  background: rgba(34, 197, 94, 0.08);
  text-align: center;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #4ade80;
  font-size: 13px;
  font-weight: 500;
}

.success-icon {
  width: 20px;
  height: 20px;
}

.upload-error {
  margin-top: 12px;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.08);
  color: #fca5a5;
  font-size: 12px;
  text-align: center;
}

.upload-results-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 160px;
  overflow-y: auto;
}

.upload-result-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 12px;
}

.upload-result-item.success {
  background: rgba(34, 197, 94, 0.06);
  color: #4ade80;
}

.upload-result-item.error {
  background: rgba(239, 68, 68, 0.06);
  color: #fca5a5;
}

.result-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.result-filename {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.result-error {
  font-size: 11px;
  opacity: 0.8;
  flex-shrink: 0;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
