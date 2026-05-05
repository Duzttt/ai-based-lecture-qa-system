<script setup>
const props = defineProps({
  hasSelection: Boolean,
  selectedCount: Number,
  selectedDocuments: Array,
  showTooltip: Boolean
})

const emit = defineEmits(['toggle-tooltip', 'close-tooltip'])
</script>

<template>
  <div v-if="hasSelection" class="retrieval-scope-wrap">
    <button
      type="button"
      class="retrieval-scope"
      :aria-expanded="showTooltip"
      aria-controls="retrieval-scope-tooltip"
      @click="emit('toggle-tooltip')"
    >
      <span class="scope-icon" aria-hidden="true">🔍</span>
      <span class="scope-label">Retrieval scope:</span>
      <span class="scope-value">
        {{ selectedCount }} document{{ selectedCount > 1 ? 's' : '' }}
        <svg class="scope-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
          <path d="M6 9l6 6 6-6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </span>
    </button>

    <div
      v-if="showTooltip"
      id="retrieval-scope-tooltip"
      class="document-tooltip"
      role="region"
      aria-label="Selected documents"
      @click.stop
    >
      <div class="tooltip-header">
        <span>📄 Selected documents</span>
        <button type="button" class="tooltip-close" aria-label="Close" @click="emit('close-tooltip')">✕</button>
      </div>
      <div class="tooltip-content">
        <div
          v-for="doc in selectedDocuments"
          :key="doc.name || doc.filename"
          class="tooltip-doc-item"
        >
          <span class="doc-icon" aria-hidden="true">📄</span>
          <span class="doc-name" :title="doc.name || doc.filename">
            {{ doc.name || doc.filename }}
          </span>
        </div>
      </div>
      <div class="tooltip-footer">
        <span class="footer-note">Click the Sources panel to change selection</span>
      </div>
    </div>
  </div>

  <div v-else class="retrieval-scope empty">
    <span class="scope-icon" aria-hidden="true">⚠️</span>
    <span class="scope-label">No documents selected</span>
  </div>
</template>

<style scoped>
.retrieval-scope-wrap {
  position: relative;
  display: inline-flex;
}

.retrieval-scope {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.15);
  border: 1px solid rgba(99, 102, 241, 0.3);
  cursor: pointer;
  transition: background-color 0.2s, border-color 0.2s;
  position: relative;
  white-space: nowrap;
  font: inherit;
  color: inherit;
  text-align: left;
}

.retrieval-scope:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.retrieval-scope:hover {
  background: rgba(99, 102, 241, 0.2);
  border-color: var(--accent);
}

.retrieval-scope.empty {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.3);
  cursor: default;
}

.retrieval-scope.empty:hover {
  background: rgba(239, 68, 68, 0.15);
}

.scope-icon {
  font-size: 12px;
}

.scope-label {
  font-size: 10px;
  color: var(--text-muted);
}

.scope-value {
  font-size: 11px;
  color: var(--accent);
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 3px;
}

.scope-chevron {
  width: 12px;
  height: 12px;
  color: var(--text-muted);
  transition: transform 0.2s;
}

.retrieval-scope:hover .scope-chevron {
  transform: rotate(180deg);
}

.document-tooltip {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 280px;
  max-height: 300px;
  background: rgba(15, 23, 42, 0.98);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 12px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6);
  z-index: 100;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  animation: slideUp 0.2s ease;
}

.tooltip-header {
  padding: 10px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-main);
  background: rgba(255, 255, 255, 0.02);
}

.tooltip-close {
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
  font-size: 14px;
  transition: background-color 0.2s, color 0.2s;
}

.tooltip-close:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.tooltip-close:hover {
  background: rgba(255, 255, 255, 0.1);
  color: white;
}

.tooltip-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tooltip-doc-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
  font-size: 11px;
  color: var(--text-main);
  transition: background-color 0.2s;
}

.tooltip-doc-item:hover {
  background: rgba(99, 102, 241, 0.15);
}

.doc-icon {
  font-size: 14px;
}

.doc-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tooltip-footer {
  padding: 8px 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(0, 0, 0, 0.2);
}

.footer-note {
  font-size: 10px;
  color: var(--text-muted);
  font-style: italic;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>