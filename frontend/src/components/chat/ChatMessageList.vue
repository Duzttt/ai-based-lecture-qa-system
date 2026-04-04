<script setup>
import ChatMessage from './ChatMessage.vue'
import RetrievalChunks from './RetrievalChunks.vue'

const props = defineProps({
  messages: Array,
  isLoading: Boolean,
  isRetrieving: Boolean,
  hasSelection: Boolean
})

const emit = defineEmits(['chunk-hover', 'chunk-click', 'chunk-rightclick', 'suggestion-click'])

const quickSuggestions = [
  'Summarize the key points',
  'Identify common themes',
  'List references',
]
</script>

<template>
  <div class="chat-body">
    <div v-if="messages.length === 0" class="chat-empty">
      <div class="empty-sparkle">
        <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M19 9l1.25-2.75L23 5l-2.75-1.25L19 1l-1.25 2.75L15 5l2.75 1.25L19 9zm-7.5.5L9 4 6.5 9.5 1 12l5.5 2.5L9 20l2.5-5.5L17 12l-5.5-2.5zM19 15l-1.25 2.75L15 19l2.75 1.25L19 23l1.25-2.75L23 19l-2.75-1.25L19 15z"/></svg>
      </div>
      <h3 class="empty-title">Ready to explore your notes.</h3>
      <p class="empty-title-line2">Ask anything about them.</p>
      <p class="empty-desc">Your academic sources are indexed and ready for deep analysis.</p>
      <div class="empty-suggestions">
        <button
          v-for="suggestion in quickSuggestions"
          :key="suggestion"
          type="button"
          class="suggestion-chip"
          @click="emit('suggestion-click', suggestion)"
        >
          {{ suggestion }}
          <svg class="chip-arrow" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
      </div>
      <div v-if="!hasSelection" class="empty-hint">
        <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>
        Select documents in the sidebar to narrow your search
      </div>
    </div>

    <div v-else class="messages-list">
      <div
        v-for="(msg, idx) in messages"
        :key="idx"
        class="message-group"
        :data-message-id="msg.id"
      >
        <ChatMessage
          :message="msg"
          @chunk-hover="(chunk) => emit('chunk-hover', chunk)"
          @chunk-click="(chunk) => emit('chunk-click', chunk)"
          @chunk-rightclick="(event, chunk) => emit('chunk-rightclick', event, chunk)"
        />
        <div v-if="msg.role === 'assistant' && msg.chunks && msg.chunks.length > 0" class="retrieval-section">
          <RetrievalChunks
            :chunks="msg.chunks"
            :loading="false"
            @chunk-hover="(chunk) => emit('chunk-hover', chunk)"
            @chunk-click="(chunk) => emit('chunk-click', chunk)"
            @chunk-rightclick="(event, chunk) => emit('chunk-rightclick', event, chunk)"
          />
        </div>
      </div>
      <div v-if="isLoading" class="message-group">
        <div class="message assistant">
          <div class="message-avatar">
            <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 3c1.93 0 3.5 1.57 3.5 3.5S13.93 13 12 13s-3.5-1.57-3.5-3.5S10.07 6 12 6zm7 13H5v-.23c0-.62.28-1.2.76-1.58C7.47 15.82 9.64 15 12 15s4.53.82 6.24 2.19c.48.38.76.97.76 1.58V19z"/></svg>
          </div>
          <div class="message-content loading" aria-live="polite">Thinking…</div>
        </div>
        <div v-if="isRetrieving" class="retrieval-section">
          <RetrievalChunks :chunks="[]" :loading="true" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-body {
  flex: 1;
  padding: 0;
  overflow-y: auto;
  position: relative;
  min-height: 0;
  background: var(--surface);
}

.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  height: 100%;
  padding: 40px 32px;
  max-width: 520px;
  margin: 0 auto;
}

.empty-sparkle {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(129, 140, 248, 0.15), rgba(189, 194, 255, 0.08));
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
}

.empty-sparkle svg {
  width: 26px;
  height: 26px;
  color: var(--primary-container);
}

.empty-title {
  font-family: var(--font-headline);
  font-size: 22px;
  font-weight: 700;
  color: var(--on-surface);
  margin: 0;
  letter-spacing: -0.02em;
}

.empty-title-line2 {
  font-family: var(--font-headline);
  font-size: 22px;
  font-weight: 700;
  color: var(--primary);
  margin: 0 0 10px;
  letter-spacing: -0.02em;
}

.empty-desc {
  font-size: 14px;
  color: var(--on-surface-variant);
  margin: 0 0 24px;
  line-height: 1.5;
}

.empty-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  margin-bottom: 20px;
}

.suggestion-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  border-radius: 10px;
  border: 1px solid rgba(69, 70, 83, 0.2);
  background: var(--surface-container);
  color: var(--on-surface);
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s, border-color 0.2s, transform 0.2s;
  white-space: nowrap;
}

.suggestion-chip:focus-visible {
  outline: 2px solid var(--primary-container);
  outline-offset: 2px;
}

.suggestion-chip:hover {
  background: var(--surface-container-high);
  border-color: rgba(129, 140, 248, 0.3);
  transform: translateY(-1px);
}

.chip-arrow {
  width: 14px;
  height: 14px;
  color: var(--primary-container);
  opacity: 0;
  transform: translateX(-4px);
  transition: opacity 0.2s, transform 0.2s;
}

.suggestion-chip:hover .chip-arrow {
  opacity: 1;
  transform: translateX(0);
}

.empty-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--on-surface-variant);
  opacity: 0.6;
}

.empty-hint svg {
  width: 16px;
  height: 16px;
}

.messages-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
}

.message-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.message {
  display: flex;
  gap: 10px;
  padding: 14px 16px;
  border-radius: 12px;
  max-width: 85%;
}

.message.user {
  align-self: flex-end;
  background: rgba(129, 140, 248, 0.12);
  margin-left: auto;
}

.message.assistant {
  align-self: flex-start;
  background: var(--surface-container-highest);
}

.message-avatar {
  font-size: 18px;
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.message-avatar svg {
  width: 20px;
  height: 20px;
  color: var(--primary-container);
}

.message-content {
  font-size: 13px;
  line-height: 1.6;
  color: var(--on-surface);
}

.message-content.loading {
  color: var(--on-surface-variant);
  font-style: italic;
}

.retrieval-section {
  width: 100%;
  max-width: 100%;
  margin-top: 4px;
}
</style>
