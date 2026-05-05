<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  summary: Object,
  config: Object,
  isLoading: Boolean,
})

const emit = defineEmits(['close', 'regenerate', 'feedback'])

const showCitations = ref(false)
const showComparison = ref(true)
const copied = ref(false)

const lengthLabels = {
  short: 'Short',
  medium: 'Medium',
  detailed: 'Detailed',
}

const styleLabels = {
  bullets: 'Bulleted',
  narrative: 'Narrative',
  academic: 'Academic',
  executive: 'Executive',
}

const languageLabels = {
  zh: 'Chinese',
  en: 'English',
}

const documentCount = computed(() => props.summary?.document_count || 1)
const hasComparison = computed(() => props.summary?.comparison && props.summary.comparison.length > 0)
const hasCitations = computed(() => props.summary?.citations && props.summary.citations.length > 0)

const copySummary = async () => {
  try {
    await navigator.clipboard.writeText(props.summary?.text || '')
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (err) {
    console.error('Failed to copy:', err)
  }
}

const exportAsMarkdown = () => {
  const docList = props.summary?.documents?.join(', ') || 'Unknown'
  const content = `# Document Summary

**Generated At**: ${new Date().toLocaleString('en-US')}
**Documents**: ${docList}
**Config**: ${lengthLabels[props.config?.length || 'medium']} | ${styleLabels[props.config?.style || 'narrative']} | ${languageLabels[props.config?.language || 'zh']}

---

${props.summary?.text || ''}

${showCitations.value && hasCitations.value ? `
## Key Citations

${props.summary.citations.map(c => `- **${c.point}**\n  > "${c.citation}"\n  — ${c.source}${c.page ? ` p.${c.page}` : ''}`).join('\n\n')}
` : ''}
`

  const blob = new Blob([content], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `summary_${Date.now()}.md`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

const handleFeedback = (rating) => {
  emit('feedback', rating)
}
</script>

<template>
  <div class="summary-viewer">
    <!-- Loading State -->
    <div v-if="isLoading" class="summary-loading">
      <div class="loading-spinner"></div>
      <div class="loading-text">Generating summary...</div>
      <div class="loading-sub">This may take a few minutes</div>
    </div>

    <!-- Summary Content -->
    <div v-else-if="summary" class="summary-content">
      <!-- Header -->
      <div class="summary-header">
        <div class="summary-meta">
          <span class="meta-badge">
            📄 {{ documentCount }} documents
          </span>
          <span class="meta-badge">
            {{ lengthLabels[config?.length || 'medium'] }} summary
          </span>
          <span class="meta-badge">
            {{ styleLabels[config?.style || 'narrative'] }} style
          </span>
        </div>
        <div class="summary-actions">
          <button @click="copySummary" class="action-btn" title="Copy summary">
            {{ copied ? '✓' : '📋' }}
          </button>
          <button @click="exportAsMarkdown" class="action-btn" title="Export Markdown">
            📥
          </button>
          <button 
            v-if="hasCitations" 
            @click="showCitations = !showCitations" 
            class="action-btn"
            :class="{ active: showCitations }"
            title="Show citations"
          >
            📌
          </button>
          <button 
            v-if="hasComparison" 
            @click="showComparison = !showComparison" 
            class="action-btn"
            :class="{ active: showComparison }"
            title="Show comparison"
          >
            ⚖
          </button>
        </div>
      </div>

      <!-- Comparison Table -->
      <div v-if="showComparison && hasComparison" class="comparison-section">
        <div class="section-header">
          <h4>📊 Document Comparison</h4>
        </div>
        <div class="comparison-table-wrapper">
          <table class="comparison-table">
            <thead>
              <tr>
                <th>Document</th>
                <th>Main Points</th>
                <th>Keywords</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(doc, idx) in summary.comparison" :key="idx" class="comparison-row">
                <td class="doc-name-cell">
                  <span class="doc-name" :title="doc.name">{{ doc.name }}</span>
                </td>
                <td class="points-cell">{{ doc.mainPoints || 'N/A' }}</td>
                <td class="keywords-cell">
                  <span v-for="(kw, kidx) in (doc.keywords || [])" :key="kidx" class="keyword-tag">
                    {{ kw }}
                  </span>
                  <span v-if="!doc.keywords || doc.keywords.length === 0" class="no-keywords">-</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Summary Text -->
      <div class="summary-text-wrapper">
        <div class="section-header">
          <h4>📝 Summary Content</h4>
        </div>
        <div class="summary-text" v-html="summary.text.replace(/\n/g, '<br>')"></div>
      </div>

      <!-- Citations -->
      <div v-if="showCitations && hasCitations" class="citations-section">
        <div class="section-header">
          <h4>📌 Key Citations</h4>
        </div>
        <div class="citations-list">
          <div v-for="(cite, idx) in summary.citations" :key="idx" class="citation-item">
            <div class="citation-point">
              <span class="point-icon">💡</span>
              <span class="point-text">{{ cite.point }}</span>
            </div>
            <div class="citation-text">
              <span class="quote-mark">"</span>
              {{ cite.citation }}
              <span class="quote-mark">"</span>
            </div>
            <div class="citation-source">
              — {{ cite.source }}<span v-if="cite.page"> p.{{ cite.page }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="summary-footer">
        <button class="regenerate-btn" @click="$emit('regenerate')" aria-label="Regenerate summary">
          🔄 Regenerate
        </button>
        <div class="feedback-section">
          <span class="feedback-label">Summary quality?</span>
          <div class="feedback-buttons">
            <button @click="handleFeedback('good')" class="feedback-btn" title="Helpful">
              👍
            </button>
            <button @click="handleFeedback('bad')" class="feedback-btn" title="Needs improvement">
              👎
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else class="summary-empty">
      <div class="empty-icon">📝</div>
      <div class="empty-text">No summary yet</div>
      <div class="empty-sub">Select documents and click Generate Summary</div>
    </div>
  </div>
</template>

<style scoped>
.summary-viewer {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

/* Loading State */
.summary-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.loading-spinner {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: 3px solid rgba(99, 102, 241, 0.2);
  border-top-color: var(--accent);
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}

.loading-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
  margin-bottom: 6px;
}

.loading-sub {
  font-size: 12px;
  color: var(--text-muted);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Summary Content */
.summary-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
  padding: 16px;
}

/* Header */
.summary-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.summary-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.meta-badge {
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.15);
  border: 1px solid rgba(99, 102, 241, 0.3);
  font-size: 11px;
  color: var(--accent);
  font-weight: 600;
  white-space: nowrap;
}

.summary-actions {
  display: flex;
  gap: 6px;
}

.action-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid rgba(55, 65, 81, 0.9);
  background: rgba(2, 6, 23, 0.6);
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  transition: all 0.2s;
}

.action-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: rgba(99, 102, 241, 0.1);
}

.action-btn.active {
  background: rgba(99, 102, 241, 0.2);
  border-color: var(--accent);
  color: var(--accent);
}

/* Comparison Section */
.comparison-section {
  background: rgba(2, 6, 23, 0.4);
  border-radius: 12px;
  border: 1px solid rgba(55, 65, 81, 0.8);
  overflow: hidden;
}

.section-header {
  padding: 10px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.section-header h4 {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.comparison-table-wrapper {
  overflow-x: auto;
}

.comparison-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.comparison-table th {
  padding: 10px 14px;
  text-align: left;
  font-weight: 600;
  color: var(--text-muted);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(0, 0, 0, 0.2);
  white-space: nowrap;
}

.comparison-table td {
  padding: 12px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
  vertical-align: top;
}

.comparison-row:hover {
  background: rgba(255, 255, 255, 0.02);
}

.doc-name-cell {
  max-width: 200px;
}

.doc-name {
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-main);
  font-weight: 500;
}

.points-cell {
  color: var(--text-main);
  line-height: 1.4;
}

.keywords-cell {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.keyword-tag {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.15);
  border: 1px solid rgba(99, 102, 241, 0.3);
  font-size: 10px;
  color: var(--accent);
  white-space: nowrap;
}

.no-keywords {
  color: var(--text-muted);
  font-style: italic;
}

/* Summary Text */
.summary-text-wrapper {
  background: rgba(2, 6, 23, 0.4);
  border-radius: 12px;
  border: 1px solid rgba(55, 65, 81, 0.8);
  overflow: hidden;
}

.summary-text {
  padding: 16px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-main);
}

/* Citations Section */
.citations-section {
  background: rgba(2, 6, 23, 0.4);
  border-radius: 12px;
  border: 1px solid rgba(55, 65, 81, 0.8);
  overflow: hidden;
}

.citations-list {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.citation-item {
  padding: 12px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.02);
  border-left: 3px solid var(--accent);
}

.citation-point {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.point-icon {
  font-size: 14px;
}

.point-text {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-main);
}

.citation-text {
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-muted);
  padding-left: 22px;
  font-style: italic;
}

.quote-mark {
  color: var(--accent);
  opacity: 0.7;
}

.citation-source {
  margin-top: 6px;
  padding-left: 22px;
  font-size: 11px;
  color: var(--text-muted);
  text-align: right;
}

/* Footer */
.summary-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.regenerate-btn {
  padding: 8px 16px;
  border-radius: 8px;
  border: 1px solid rgba(99, 102, 241, 0.4);
  background: rgba(99, 102, 241, 0.1);
  color: var(--accent);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 6px;
}

.regenerate-btn:hover {
  background: rgba(99, 102, 241, 0.2);
  border-color: var(--accent);
}

.feedback-section {
  display: flex;
  align-items: center;
  gap: 10px;
}

.feedback-label {
  font-size: 11px;
  color: var(--text-muted);
}

.feedback-buttons {
  display: flex;
  gap: 6px;
}

.feedback-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid rgba(55, 65, 81, 0.9);
  background: rgba(2, 6, 23, 0.6);
  cursor: pointer;
  font-size: 16px;
  transition: all 0.2s;
}

.feedback-btn:hover {
  border-color: var(--accent);
  transform: scale(1.1);
}

/* Empty State */
.summary-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
  opacity: 0.5;
}

.empty-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
  margin-bottom: 6px;
}

.empty-sub {
  font-size: 12px;
  color: var(--text-muted);
}
</style>
