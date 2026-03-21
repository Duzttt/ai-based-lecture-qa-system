<script setup>
import { ref } from 'vue'
import RetrievalScopeIndicator from './RetrievalScopeIndicator.vue'

const props = defineProps({
  hasSelection: Boolean,
  selectedCount: Number,
  selectedDocuments: Array
})

const showDocumentListTooltip = ref(false)

const toggleDocumentListTooltip = () => {
  showDocumentListTooltip.value = !showDocumentListTooltip.value
}
</script>

<template>
  <div class="chat-header">
    <div class="chat-title">
      <span class="chat-title-main">Chat</span>
      <span class="chat-title-sub">Ask anything about your notes</span>
    </div>
    
    <RetrievalScopeIndicator
      :has-selection="hasSelection"
      :selected-count="selectedCount"
      :selected-documents="selectedDocuments"
      :show-tooltip="showDocumentListTooltip"
      @toggle-tooltip="toggleDocumentListTooltip"
      @close-tooltip="showDocumentListTooltip = false"
    />
  </div>
</template>

<style scoped>
.chat-header {
  padding: 10px 14px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.9);
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.chat-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.chat-title-main {
  font-size: 13px;
  font-weight: 600;
}

.chat-title-sub {
  font-size: 11px;
  color: var(--text-muted);
}
</style>