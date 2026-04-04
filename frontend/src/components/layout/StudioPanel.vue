<script setup>
import { ref, computed } from 'vue'
import { useDocumentStore } from '../../stores/documentStore'
import { useSummaryStore } from '../../stores/summaryStore'
import SummaryModal from '../studio/SummaryModal.vue'
import SummaryViewer from '../studio/SummaryViewer.vue'

const documentStore = useDocumentStore()
const summaryStore = useSummaryStore()

const studioTools = [
  {
    id: 'summary',
    title: 'Summarize PDF',
    desc: 'Condense complex papers into high-level editorial abstracts.',
    icon: 'M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z',
    action: 'summary',
  },
  {
    id: 'quiz',
    title: 'Create Quiz',
    desc: 'Generate active recall tests based on your selected sources.',
    icon: 'M18 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM9 4h2v5l-1-.75L9 9V4zm9 16H6V4h1v9l3-2.25L13 13V4h5v16z',
    action: 'quiz',
    disabled: true,
  },
  {
    id: 'flashcards',
    title: 'Study Cards',
    desc: 'Convert lecture notes into digital flashcards automatically.',
    icon: 'M4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H8V4h12v12z',
    action: 'flashcards',
    disabled: true,
  },
]

const showSummaryModal = ref(false)
const showSummaryViewer = ref(false)

const selectedDocs = computed(() => documentStore.selectedDocIds)
const selectedCount = computed(() => selectedDocs.value.length)
const currentSummary = computed(() => summaryStore.currentSummary)
const isGenerating = computed(() => summaryStore.isGenerating)

const handleToolClick = (tool) => {
  if (tool.disabled) return
  if (tool.action === 'summary') {
    openSummaryModal()
  }
}

const openSummaryModal = () => {
  if (selectedCount.value === 0) {
    alert('Please select at least one document in the sidebar first')
    return
  }
  showSummaryModal.value = true
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
}

const closeSummaryViewer = () => {
  showSummaryViewer.value = false
  summaryStore.clearCurrent()
}
</script>

<template>
  <div class="panel studio-panel">
    <div class="panel-header">
      <h2 class="panel-title">Studio Tools</h2>
    </div>

    <div class="panel-body">
      <div class="tools-list">
        <button
          v-for="tool in studioTools"
          :key="tool.id"
          type="button"
          class="tool-card"
          :class="{ disabled: tool.disabled }"
          :disabled="tool.disabled"
          @click="handleToolClick(tool)"
        >
          <div class="tool-icon-wrap">
            <svg class="tool-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path :d="tool.icon" /></svg>
          </div>
          <div class="tool-content">
            <span class="tool-title">{{ tool.title }}</span>
            <span class="tool-desc">{{ tool.desc }}</span>
          </div>
          <span v-if="tool.action === 'summary' && selectedCount > 0" class="tool-badge" aria-hidden="true">
            {{ selectedCount }}
          </span>
        </button>
      </div>

      <div v-if="showSummaryViewer" class="summary-viewer-container">
        <div class="viewer-header">
          <span class="viewer-title">Summary</span>
          <button type="button" class="viewer-close" aria-label="Close summary" @click="closeSummaryViewer">
            <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
          </button>
        </div>
        <SummaryViewer
          :summary="currentSummary"
          :config="summaryStore.lastConfig"
          :is-loading="isGenerating"
          @regenerate="handleSummaryRegenerate"
          @feedback="handleSummaryFeedback"
        />
      </div>

      <div class="pro-section">
        <div class="pro-header">
          <svg class="pro-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/></svg>
          <span class="pro-title">Deep Focus Mode</span>
        </div>
        <span class="pro-badge">Pro Feature</span>
        <button type="button" class="pro-btn" aria-label="Upgrade workspace (coming soon)" disabled>
          <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
          Upgrade Workspace
        </button>
      </div>
    </div>

    <SummaryModal
      v-model:show="showSummaryModal"
      :selected-docs="selectedDocs"
      @generate="handleSummaryGenerate"
      @close="showSummaryModal = false"
    />
  </div>
</template>

<style scoped>
.studio-panel {
  background: var(--surface-container-low);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.panel-header {
  padding: 16px 16px 12px;
}

.panel-title {
  font-family: var(--font-headline);
  font-size: 14px;
  font-weight: 600;
  color: var(--on-surface-variant);
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.panel-body {
  flex: 1;
  padding: 0 12px 12px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tools-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tool-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 12px;
  border-radius: 10px;
  border: none;
  width: 100%;
  text-align: left;
  background: var(--surface-container);
  cursor: pointer;
  transition: background-color 0.2s;
  position: relative;
  font: inherit;
  color: inherit;
}

.tool-card:focus-visible {
  outline: 2px solid var(--primary-container);
  outline-offset: 2px;
}

.tool-card:disabled {
  cursor: not-allowed;
}

.tool-card:hover:not(.disabled) {
  background: var(--surface-container-high);
}

.tool-card.disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.tool-icon-wrap {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(129, 140, 248, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.tool-icon {
  width: 20px;
  height: 20px;
  color: var(--primary-container);
}

.tool-card.disabled .tool-icon-wrap {
  background: rgba(69, 70, 83, 0.15);
}

.tool-card.disabled .tool-icon {
  color: var(--on-surface-variant);
}

.tool-content {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.tool-title {
  font-family: var(--font-headline);
  font-size: 13px;
  font-weight: 600;
  color: var(--on-surface);
}

.tool-desc {
  font-size: 11px;
  color: var(--on-surface-variant);
  line-height: 1.4;
}

.tool-badge {
  position: absolute;
  top: 10px;
  right: 10px;
  min-width: 20px;
  height: 20px;
  border-radius: 10px;
  background: var(--primary-container);
  color: var(--on-primary);
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 6px;
}

.summary-viewer-container {
  border-radius: 10px;
  background: var(--surface-container);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: 400px;
}

.viewer-header {
  padding: 10px 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(129, 140, 248, 0.06);
}

.viewer-title {
  font-family: var(--font-headline);
  font-size: 13px;
  font-weight: 600;
  color: var(--primary);
}

.viewer-close {
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
  transition: background-color 0.2s, color 0.2s;
}

.viewer-close:focus-visible {
  outline: 2px solid var(--primary-container);
  outline-offset: 2px;
}

.viewer-close svg {
  width: 16px;
  height: 16px;
}

.viewer-close:hover {
  background: rgba(255, 255, 255, 0.06);
  color: var(--on-surface);
}

.pro-section {
  margin-top: auto;
  padding: 16px;
  border-radius: 10px;
  background: var(--surface-container);
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: flex-start;
}

.pro-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pro-icon {
  width: 18px;
  height: 18px;
  color: var(--tertiary);
}

.pro-title {
  font-family: var(--font-headline);
  font-size: 14px;
  font-weight: 600;
  color: var(--on-surface);
}

.pro-badge {
  padding: 3px 10px;
  border-radius: 6px;
  background: rgba(247, 189, 62, 0.1);
  color: var(--tertiary);
  font-size: 11px;
  font-weight: 600;
}

.pro-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: 8px;
  border: none;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-container) 100%);
  color: var(--on-primary);
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s, opacity 0.2s;
}

.pro-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.pro-btn:focus-visible:not(:disabled) {
  outline: 2px solid var(--primary);
  outline-offset: 2px;
}

.pro-btn svg {
  width: 16px;
  height: 16px;
}

.pro-btn:hover {
  box-shadow: 0 4px 16px rgba(129, 140, 248, 0.25);
  transform: translateY(-1px);
}
</style>
