<script setup>
import { ref } from 'vue'

const props = defineProps({
  documents: Array,
  documentsLoading: Boolean,
  documentSearch: String,
  selectedDoc: Object,
  documentChunks: Array,
  chunksLoading: Boolean,
  currentPage: Number,
  pageSize: Number,
  totalChunks: Number
})

const emit = defineEmits([
  'update:documentSearch',
  'load-documents',
  'view-chunks',
  'view-analytics',
  'reindex-document',
  'delete-document',
  'close-chunks',
  'load-chunks'
])

const formatSize = (kb) => {
  if (kb < 1024) return `${kb.toFixed(1)} KB`
  return `${(kb / 1024).toFixed(2)} MB`
}
</script>

<template>
  <div class="tab-content">
    <!-- Document List -->
    <div v-if="!selectedDoc" class="documents-section">
      <div class="docs-header">
        <h3 class="section-title">Indexed Documents</h3>
        <div class="docs-search">
          <input
            :value="documentSearch"
            @input="emit('update:documentSearch', $event.target.value)"
            type="text"
            placeholder="Search documents..."
            class="search-input"
            @keyup.enter="emit('load-documents')"
          />
          <button class="refresh-btn" @click="emit('load-documents')" aria-label="Refresh documents">↻</button>
        </div>
      </div>

      <div v-if="documentsLoading" class="loading-small">Loading...</div>
      
      <div v-else class="docs-list">
        <div v-for="doc in documents" :key="doc.id" class="doc-item">
          <div class="doc-info">
            <div class="doc-name">{{ doc.name }}</div>
            <div class="doc-meta">
              {{ formatSize(doc.size_kb) }} · {{ doc.chunk_count }} chunks
            </div>
            <div class="doc-date">{{ new Date(doc.created_at).toLocaleString() }}</div>
          </div>
          <div class="doc-actions">
            <button class="action-btn view" @click="emit('view-chunks', doc)">Chunks</button>
            <button class="action-btn analytics" @click="emit('view-analytics', doc)">Analytics</button>
            <button class="action-btn reindex" @click="emit('reindex-document', doc.id)">Reindex</button>
            <button class="action-btn delete" @click="emit('delete-document', doc.id)">Delete</button>
          </div>
        </div>
        
        <div v-if="documents.length === 0" class="empty-state">
          No documents found
        </div>
      </div>
    </div>

    <!-- Chunk Browser -->
    <div v-else class="chunks-section">
      <div class="chunks-header">
        <button class="back-btn" @click="emit('close-chunks')">← Back</button>
        <h3 class="section-title">{{ selectedDoc.name }}</h3>
        <span class="chunks-count">{{ totalChunks }} chunks</span>
      </div>

      <div v-if="chunksLoading" class="loading-small">Loading chunks...</div>
      
      <div v-else class="chunks-list">
        <div v-for="chunk in documentChunks" :key="chunk.index" class="chunk-item">
          <div class="chunk-header">
            <span class="chunk-index">#{{ chunk.index }}</span>
            <span v-if="chunk.page" class="chunk-page">Page {{ chunk.page }}</span>
          </div>
          <div class="chunk-text">{{ chunk.text }}</div>
          <div v-if="chunk.embedding_preview" class="chunk-embedding">
            Embedding: [{{ chunk.embedding_preview.join(', ') }}...]
          </div>
        </div>
      </div>

      <!-- Pagination -->
      <div v-if="totalChunks > pageSize" class="pagination">
        <button
          :disabled="currentPage === 1"
          @click="emit('load-chunks', selectedDoc.id, currentPage - 1)"
        >
          Previous
        </button>
        <span class="page-info">Page {{ currentPage }} of {{ Math.ceil(totalChunks / pageSize) }}</span>
        <button
          :disabled="currentPage >= Math.ceil(totalChunks / pageSize)"
          @click="emit('load-chunks', selectedDoc.id, currentPage + 1)"
        >
          Next
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tab-content {
  padding: 20px;
}

.documents-section, .chunks-section {
  height: 100%;
}

.docs-header, .chunks-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  gap: 12px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: white;
  margin: 0;
}

.docs-search {
  display: flex;
  gap: 8px;
}

.search-input {
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid rgba(55, 65, 81, 0.8);
  background: rgba(2, 6, 23, 0.8);
  color: var(--text-main);
  font-size: 13px;
  outline: none;
  width: 200px;
}

.search-input:focus {
  border-color: var(--accent);
}

.refresh-btn, .back-btn {
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-muted);
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.refresh-btn:hover, .back-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: white;
}

.loading-small {
  text-align: center;
  padding: 40px;
  color: var(--text-muted);
}

.docs-list, .chunks-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: calc(100vh - 300px);
  overflow-y: auto;
}

.doc-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 10px;
  transition: all 0.2s;
}

.doc-item:hover {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(99, 102, 241, 0.3);
}

.doc-info {
  flex: 1;
  min-width: 0;
}

.doc-name {
  font-size: 13px;
  font-weight: 600;
  color: white;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.doc-meta {
  font-size: 11px;
  color: var(--text-muted);
}

.doc-date {
  font-size: 10px;
  color: var(--text-muted);
  margin-top: 2px;
}

.doc-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.action-btn {
  padding: 6px 10px;
  border-radius: 6px;
  border: none;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn.view {
  background: rgba(99, 102, 241, 0.2);
  color: var(--accent);
}

.action-btn.analytics {
  background: rgba(168, 85, 247, 0.2);
  color: #a855f7;
}

.action-btn.reindex {
  background: rgba(34, 197, 94, 0.2);
  color: #22c55e;
}

.action-btn.delete {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}

.action-btn:hover {
  filter: brightness(1.2);
}

.chunk-item {
  padding: 12px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 8px;
}

.chunk-header {
  display: flex;
  gap: 12px;
  margin-bottom: 8px;
}

.chunk-index {
  font-size: 11px;
  font-weight: 600;
  color: var(--accent);
}

.chunk-page {
  font-size: 11px;
  color: var(--text-muted);
}

.chunk-text {
  font-size: 12px;
  color: var(--text-main);
  line-height: 1.5;
  white-space: pre-wrap;
}

.chunk-embedding {
  font-size: 10px;
  color: var(--text-muted);
  margin-top: 8px;
  font-family: monospace;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.pagination button {
  padding: 8px 16px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-main);
  cursor: pointer;
  transition: all 0.2s;
}

.pagination button:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.2);
  border-color: var(--accent);
}

.pagination button:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.page-info {
  font-size: 12px;
  color: var(--text-muted);
}

.chunks-count {
  font-size: 12px;
  color: var(--text-muted);
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: var(--text-muted);
  font-size: 13px;
}
</style>