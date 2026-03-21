<script setup>
import { ref, computed, defineEmits } from 'vue'
import { compareDocuments as compareDocumentsApi } from '../../services/api'

const emit = defineEmits(['close', 'save-comparison'])

const props = defineProps({
  selectedDocs: {
    type: Array,
    default: () => [],
  },
})

const query = ref('')
const isLoading = ref(false)
const error = ref('')
const results = ref([])
const analysis = ref(null)
const hasRunComparison = ref(false)

const columnStyle = computed(() => {
  const count = results.value.length || props.selectedDocs.length
  if (count <= 1) return '1fr'
  if (count === 2) return 'repeat(2, 1fr)'
  return 'repeat(3, 1fr)'
})

const runComparison = async () => {
  if (!query.value.trim()) {
    error.value = 'Please enter a question'
    return
  }
  if (props.selectedDocs.length < 2) {
    error.value = 'Please select at least 2 documents'
    return
  }

  isLoading.value = true
  error.value = ''
  results.value = []
  analysis.value = null

  try {
    const data = await compareDocumentsApi(query.value, props.selectedDocs)
    results.value = data.results || []
    analysis.value = data.analysis || null
    hasRunComparison.value = true
  } catch (err) {
    error.value = err.message || 'Failed to run comparison'
  } finally {
    isLoading.value = false
  }
}

const highlightDifferences = (text, type) => {
  if (!text) return text
  
  // Simple highlighting based on type
  const commonClass = 'diff-common'
  const diffClass = 'diff-different'
  
  // This is a simplified version - real implementation would use the analysis data
  return text
}

const saveAsNote = () => {
  const content = {
    query: query.value,
    documents: props.selectedDocs,
    results: results.value,
    analysis: analysis.value,
    timestamp: new Date().toISOString()
  }
  
  const notes = JSON.parse(localStorage.getItem('comparison_notes') || '[]')
  notes.push(content)
  localStorage.setItem('comparison_notes', JSON.stringify(notes))
  
  emit('save-comparison', content)
  alert('Comparison saved as note!')
}

const exportAsMarkdown = () => {
  let md = `# Document Comparison\n\n`
  md += `**Question:** ${query.value}\n\n`
  md += `**Documents:** ${props.selectedDocs.join(', ')}\n\n`
  md += `**Date:** ${new Date().toLocaleString()}\n\n---\n\n`
  
  results.value.forEach(result => {
    md += `## ${result.source}\n\n`
    md += `${result.answer}\n\n---\n\n`
  })
  
  if (analysis.value) {
    md += `## Analysis\n\n`
    if (analysis.value.common) {
      md += `### Common Points\n`
      analysis.value.common.forEach((point, i) => {
        md += `${i + 1}. ${point}\n`
      })
      md += `\n`
    }
    if (analysis.value.different) {
      md += `### Different Points\n`
      analysis.value.different.forEach((point, i) => {
        md += `${i + 1}. ${point}\n`
      })
      md += `\n`
    }
  }
  
  const blob = new Blob([md], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `comparison_${Date.now()}.md`
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="comparison-view">
    <div class="comparison-header">
      <div class="comparison-input-wrap">
        <input
          v-model="query"
          type="text"
          class="comparison-input"
          placeholder="Enter question to compare across documents..."
          @keydown.enter="runComparison"
        />
        <button
          class="comparison-submit-btn"
          @click="runComparison"
          :disabled="isLoading || selectedDocs.length < 2"
        >
          ⚡ Compare
        </button>
      </div>
      
      <div class="comparison-docs-info">
        <span class="docs-count">{{ selectedDocs.length }} documents:</span>
        <div class="docs-list">
          <span v-for="doc in selectedDocs" :key="doc" class="doc-tag">
            📄 {{ doc.split('/').pop() }}
          </span>
        </div>
      </div>
      
      <div class="comparison-actions" v-if="hasRunComparison">
        <button class="action-btn" @click="saveAsNote">💾 Save</button>
        <button class="action-btn" @click="exportAsMarkdown">📤 Export</button>
        <button class="action-btn close-btn" @click="emit('close')">✕ Close</button>
      </div>
    </div>

    <div v-if="error" class="comparison-error">{{ error }}</div>

    <div v-if="isLoading" class="comparison-loading">
      <div class="loading-spinner"></div>
      <span>Analyzing documents...</span>
    </div>

    <div v-else-if="hasRunComparison && results.length > 0" class="comparison-body">
      <div class="comparison-columns" :style="{ gridTemplateColumns: columnStyle }">
        <div
          v-for="(result, idx) in results"
          :key="result.source"
          class="comparison-column"
        >
          <div class="comparison-column-header">
            <div class="comparison-column-title">
              <span class="doc-icon">📄</span>
              <span class="doc-name">{{ result.source.split('/').pop() }}</span>
            </div>
            <span v-if="result.success" class="status-badge success">✓</span>
            <span v-else class="status-badge error">✕</span>
          </div>
          <div class="comparison-column-body">
            <p v-if="!result.success" class="error-message">{{ result.answer }}</p>
            <div v-else class="answer-content">{{ result.answer }}</div>
          </div>
        </div>
      </div>

      <!-- Analysis Section -->
      <div v-if="analysis" class="difference-analysis">
        <div class="difference-header">
          <span class="difference-title">
            <span>🔍</span>
            Difference Analysis
          </span>
        </div>
        
        <div class="difference-summary-cards" v-if="analysis.summary">
          <div class="summary-card">
            <div class="summary-value">{{ analysis.summary.total_common || 0 }}</div>
            <div class="summary-label">Common Points</div>
          </div>
          <div class="summary-card">
            <div class="summary-value">{{ analysis.summary.total_different || 0 }}</div>
            <div class="summary-label">Differences</div>
          </div>
          <div class="summary-card">
            <div class="summary-value">{{ analysis.summary.similarity_score || 'N/A' }}</div>
            <div class="summary-label">Similarity</div>
          </div>
        </div>

        <div class="analysis-content">
          <div v-if="analysis.common_points && analysis.common_points.length" class="analysis-section">
            <h4 class="section-title common">📌 Common Information</h4>
            <ul class="points-list">
              <li v-for="(point, idx) in analysis.common_points" :key="idx" class="point-item common">
                {{ point }}
              </li>
            </ul>
          </div>
          
          <div v-if="analysis.different_points && analysis.different_points.length" class="analysis-section">
            <h4 class="section-title different">⚠️ Differences</h4>
            <ul class="points-list">
              <li v-for="(point, idx) in analysis.different_points" :key="idx" class="point-item different">
                {{ point }}
              </li>
            </ul>
          </div>

          <div v-if="analysis.summary_text" class="analysis-summary">
            <h4 class="section-title">📊 Summary</h4>
            <p class="summary-text">{{ analysis.summary_text }}</p>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="comparison-empty">
      <div class="empty-icon">⚖</div>
      <div class="empty-title">Document Comparison</div>
      <div class="empty-desc">
        Select 2-3 documents from the left panel and enter a question to compare answers.
      </div>
    </div>
  </div>
</template>

<style scoped>
.comparison-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: linear-gradient(
    135deg,
    rgba(15, 25, 45, 0.3) 0%,
    rgba(25, 35, 60, 0.4) 100%
  );
  border-radius: var(--radius-lg);
  border: 1px solid rgba(255, 255, 255, 0.08);
  padding: 16px;
}

.comparison-header {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.comparison-input-wrap {
  display: flex;
  gap: 8px;
}

.comparison-input {
  flex: 1;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid rgba(55, 65, 81, 0.8);
  background: rgba(2, 6, 23, 0.8);
  color: var(--text-main);
  font-size: 13px;
  outline: none;
  transition: all 0.2s;
}

.comparison-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.comparison-submit-btn {
  padding: 10px 20px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(135deg, var(--accent), #a855f7);
  color: white;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.comparison-submit-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 8px 20px -10px rgba(99, 102, 241, 0.5);
}

.comparison-submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.comparison-docs-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.docs-count {
  font-size: 11px;
  color: var(--text-muted);
}

.docs-list {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.doc-tag {
  font-size: 11px;
  padding: 3px 8px;
  background: rgba(99, 102, 241, 0.15);
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: 999px;
  color: var(--text-main);
}

.comparison-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-main);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.2);
}

.close-btn:hover {
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.3);
}

.comparison-error {
  padding: 10px 14px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  color: #fca5a5;
  font-size: 12px;
  margin-bottom: 16px;
}

.comparison-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  gap: 16px;
  color: var(--text-muted);
}

.loading-spinner {
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

.comparison-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow: hidden;
}

.comparison-columns {
  display: grid;
  gap: 12px;
  flex: 1;
  min-height: 0;
}

.comparison-column {
  display: flex;
  flex-direction: column;
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid rgba(55, 65, 81, 0.6);
  border-radius: 12px;
  overflow: hidden;
}

.comparison-column-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: rgba(0, 0, 0, 0.2);
  border-bottom: 1px solid rgba(55, 65, 81, 0.5);
  flex-shrink: 0;
}

.comparison-column-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
  color: white;
}

.doc-icon {
  font-size: 14px;
}

.doc-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.status-badge {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}

.status-badge.success {
  background: rgba(34, 197, 94, 0.2);
  color: #22c55e;
  border: 1px solid rgba(34, 197, 94, 0.3);
}

.status-badge.error {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.comparison-column-body {
  flex: 1;
  padding: 12px;
  overflow-y: auto;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-main);
}

.answer-content {
  white-space: pre-wrap;
}

.error-message {
  color: #fca5a5;
}

.difference-analysis {
  margin-top: 14px;
  padding: 14px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(55, 65, 81, 0.6);
  border-radius: 12px;
}

.difference-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.difference-title {
  font-size: 13px;
  font-weight: 600;
  color: white;
  display: flex;
  align-items: center;
  gap: 8px;
}

.difference-summary-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 16px;
}

.summary-card {
  padding: 12px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  text-align: center;
}

.summary-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--accent);
}

.summary-label {
  font-size: 10px;
  color: var(--text-muted);
  margin-top: 4px;
}

.analysis-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.analysis-section {
  padding: 12px;
  background: rgba(0, 0, 0, 0.15);
  border-radius: 8px;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.section-title.common {
  color: #60a5fa;
}

.section-title.different {
  color: #fbbf24;
}

.points-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.point-item {
  font-size: 12px;
  padding: 8px 12px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
  border-left: 3px solid var(--text-muted);
}

.point-item.common {
  border-left-color: #60a5fa;
  background: rgba(96, 165, 250, 0.05);
}

.point-item.different {
  border-left-color: #fbbf24;
  background: rgba(251, 191, 36, 0.05);
}

.analysis-summary {
  padding: 12px;
  background: rgba(99, 102, 241, 0.1);
  border-radius: 8px;
  border: 1px solid rgba(99, 102, 241, 0.2);
}

.summary-text {
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-main);
}

.comparison-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 40px;
  text-align: center;
  color: var(--text-muted);
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-main);
  margin-bottom: 8px;
}

.empty-desc {
  font-size: 13px;
  line-height: 1.5;
  max-width: 300px;
}

/* Responsive */
@media (max-width: 900px) {
  .comparison-columns {
    grid-template-columns: 1fr !important;
  }
  
  .comparison-header {
    flex-direction: column;
  }
  
  .comparison-input-wrap {
    flex-direction: column;
  }
  
  .comparison-submit-btn {
    width: 100%;
  }
}
</style>
