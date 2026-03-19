<script setup>
import { ref, computed } from 'vue'
import { useDocumentStore } from '../../stores/documentStore'
import { useSummaryStore } from '../../stores/summaryStore'
import EmbeddingModelSelector from '../settings/EmbeddingModelSelector.vue'
import ModelComparison from '../dashboard/ModelComparison.vue'
import SummaryModal from '../studio/SummaryModal.vue'
import SummaryViewer from '../studio/SummaryViewer.vue'

const documentStore = useDocumentStore()
const summaryStore = useSummaryStore()

const studioOptions = [
  { id: 1, title: '📝 文档摘要', sub: '生成选中文档的智能摘要', action: 'summary' },
  { id: 2, title: '📚 测验', sub: '创建知识测验', action: 'quiz' },
  { id: 3, title: '🃏 抽认卡', sub: '学习卡片', action: 'flashcards' },
  { id: 4, title: '🎙️ 播客', sub: '音频笔记', action: 'podcast' },
]

const showModelComparison = ref(false)
const showSummaryModal = ref(false)
const showSummaryViewer = ref(false)

const selectedDocs = computed(() => documentStore.selectedDocIds)
const selectedCount = computed(() => selectedDocs.value.length)
const currentSummary = computed(() => summaryStore.currentSummary)
const isGenerating = computed(() => summaryStore.isGenerating)

const handleStudioClick = (option) => {
  if (option.action === 'summary') {
    openSummaryModal()
  } else {
    // Placeholder for other features
    alert(`${option.title} 功能开发中...`)
  }
}

const openSummaryModal = () => {
  if (selectedCount.value === 0) {
    alert('请先在 Sources 面板中选择至少一个文档')
    return
  }
  showSummaryModal.value = true
}

const closeSummaryModal = () => {
  showSummaryModal.value = false
}

const handleSummaryGenerate = async (config) => {
  await summaryStore.generate(selectedDocs.value, config)
  showSummaryModal.value = false
  showSummaryViewer.value = true
}

const handleSummaryRegenerate = async () => {
  if (currentSummary.value?.history_id) {
    const newConfig = summaryStore.lastConfig || {}
    await summaryStore.regenerate(currentSummary.value.history_id, newConfig)
  }
}

const handleSummaryFeedback = (rating) => {
  console.log('Feedback:', rating)
  // TODO: Send feedback to backend
}

const closeSummaryViewer = () => {
  showSummaryViewer.value = false
  summaryStore.clearCurrent()
}

const handleModelChanged = (model) => {
  console.log('Model changed to:', model)
}

const openModelComparison = () => {
  showModelComparison.value = true
}

const closeModelComparison = () => {
  showModelComparison.value = false
}
</script>

<template>
  <div class="panel studio-panel">
    <div class="panel-header">
      <div>
        <span class="panel-header-title">Studio</span>
        <span class="panel-header-sub">AI Tools</span>
      </div>
    </div>
    <div class="studio-body">
      <!-- Embedding Model Selector -->
      <EmbeddingModelSelector @model-changed="handleModelChanged" />
      
      <!-- Studio Tools Grid -->
      <div class="studio-grid">
        <div
          v-for="option in studioOptions"
          :key="option.id"
          class="studio-card"
          :class="{ 'disabled': option.action !== 'summary' }"
          @click="handleStudioClick(option)"
        >
          <span class="title">{{ option.title }}</span>
          <span class="sub">{{ option.sub }}</span>
          <span v-if="option.action === 'summary' && selectedCount > 0" class="doc-count-badge">
            {{ selectedCount }} 文档
          </span>
        </div>
      </div>
      
      <!-- Summary Viewer -->
      <div v-if="showSummaryViewer" class="summary-viewer-container">
        <div class="viewer-header">
          <span class="viewer-title">摘要查看</span>
          <button class="viewer-close" @click="closeSummaryViewer">✕</button>
        </div>
        <SummaryViewer
          :summary="currentSummary"
          :config="summaryStore.lastConfig"
          :is-loading="isGenerating"
          @regenerate="handleSummaryRegenerate"
          @feedback="handleSummaryFeedback"
        />
      </div>
      
      <!-- Studio Footer -->
      <div class="studio-footer">
        <button class="btn-compare-models" @click="openModelComparison">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="16" height="16">
            <path d="M18 20V10M12 20V4M6 20v-6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          对比模型
        </button>
        <span class="tools-hint">更多工具即将推出...</span>
      </div>
    </div>
    
    <!-- Model Comparison Modal -->
    <ModelComparison 
      v-model:show="showModelComparison" 
      @close="closeModelComparison" 
    />
    
    <!-- Summary Configuration Modal -->
    <SummaryModal
      v-model:show="showSummaryModal"
      :selected-docs="selectedDocs"
      @generate="handleSummaryGenerate"
      @close="closeSummaryModal"
    />
  </div>
</template>

<style scoped>
.studio-panel {
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
}

.studio-panel:hover {
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

.panel-header-title {
  font-weight: 600;
}

.panel-header-sub {
  font-size: 11px;
  color: var(--text-muted);
}

.studio-body {
  padding: calc(var(--spacing-unit) + 2px);
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 12px;
}

.studio-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.studio-card {
  padding: 10px 10px;
  border-radius: 10px;
  border: 1px solid var(--border-strong);
  background: #020617;
  display: flex;
  flex-direction: column;
  gap: 4px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.studio-card:hover:not(.disabled) {
  transform: translateY(-2px);
  border-color: var(--accent);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.8);
}

.studio-card.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.studio-card.disabled:hover {
  transform: none;
  border-color: var(--border-strong);
  box-shadow: none;
}

.studio-card span.title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-main);
}

.studio-card span.sub {
  font-size: 10px;
  color: var(--text-muted);
}

.doc-count-badge {
  position: absolute;
  top: 6px;
  right: 6px;
  padding: 2px 6px;
  border-radius: 6px;
  background: rgba(99, 102, 241, 0.2);
  border: 1px solid rgba(99, 102, 241, 0.4);
  font-size: 9px;
  color: var(--accent);
  font-weight: 600;
}

/* Summary Viewer Container */
.summary-viewer-container {
  margin-top: 8px;
  border-radius: 10px;
  border: 1px solid rgba(99, 102, 241, 0.3);
  background: rgba(99, 102, 241, 0.05);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: 500px;
}

.viewer-header {
  padding: 8px 12px;
  border-bottom: 1px solid rgba(99, 102, 241, 0.2);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(99, 102, 241, 0.1);
}

.viewer-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--accent);
}

.viewer-close {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  transition: all 0.2s;
}

.viewer-close:hover {
  background: rgba(255, 255, 255, 0.1);
  color: white;
}

.studio-footer {
  margin-top: 10px;
  padding: 8px 8px 10px;
  border-radius: 10px;
  border: 1px dashed rgba(55, 65, 81, 0.9);
  background: rgba(15, 23, 42, 0.6);
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
}

.btn-compare-models {
  padding: 8px 16px;
  border-radius: 10px;
  border: 1px solid rgba(99, 102, 241, 0.5);
  background: rgba(99, 102, 241, 0.1);
  color: var(--accent);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.2s;
}

.btn-compare-models:hover {
  background: rgba(99, 102, 241, 0.2);
  border-color: var(--accent);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.2);
}

.tools-hint {
  font-size: 10px;
  color: var(--text-muted);
}
</style>
