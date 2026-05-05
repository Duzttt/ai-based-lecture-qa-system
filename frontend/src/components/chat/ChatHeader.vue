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
      <h2 class="chat-title-main">Chat</h2>
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
  padding: 14px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background: var(--surface-container);
}

.chat-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.chat-title-main {
  font-family: var(--font-headline);
  font-size: 15px;
  font-weight: 600;
  color: var(--on-surface);
  margin: 0;
}

.chat-title-sub {
  font-size: 12px;
  color: var(--on-surface-variant);
}
</style>
