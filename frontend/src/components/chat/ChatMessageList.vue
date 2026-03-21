<script setup>
import ChatMessage from './ChatMessage.vue'
import RetrievalChunks from './RetrievalChunks.vue'

const props = defineProps({
  messages: Array,
  isLoading: Boolean,
  isRetrieving: Boolean,
  hasSelection: Boolean
})

const emit = defineEmits(['chunk-hover', 'chunk-click', 'chunk-rightclick'])
</script>

<template>
  <div class="chat-body">
    <div v-if="messages.length === 0" class="chat-empty-card">
      <div class="chat-empty-icon">💬</div>
      <div class="chat-empty-title">Start a Conversation</div>
      <div class="chat-empty-desc">Ask questions about your lecture notes</div>
      <div v-if="!hasSelection" class="empty-warning">
        <span class="warning-icon">⚠️</span>
        <span class="warning-text">Please select documents to search on the left</span>
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
          <div class="message-avatar">🤖</div>
          <div class="message-content loading">Thinking...</div>
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
  padding: 14px;
  overflow-y: auto;
  position: relative;
  min-height: 0;
}

.chat-empty-card {
  margin: 0 auto;
  margin-top: 10%;
  max-width: 260px;
  text-align: center;
  padding: 16px 14px 18px;
  border-radius: 18px;
  background: linear-gradient(
    145deg,
    rgba(25, 35, 55, 0.5) 0%,
    rgba(15, 25, 45, 0.6) 100%
  );
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-top-color: rgba(255, 255, 255, 0.2);
  border-left-color: rgba(255, 255, 255, 0.2);
  box-shadow:
    0 25px 40px -20px black,
    inset -2px -2px 5px rgba(0, 0, 0, 0.3),
    inset 2px 2px 5px rgba(255, 255, 255, 0.1);
}

.chat-empty-icon {
  width: 40px;
  height: 40px;
  border-radius: 16px;
  margin: 0 auto 10px;
  background: radial-gradient(circle at 20% 0, #a855f7, #22c55e);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #020617;
  font-size: 20px;
}

.chat-empty-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 4px;
}

.chat-empty-desc {
  font-size: 12px;
  color: var(--text-muted);
}

.empty-warning {
  margin-top: 12px;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.warning-icon {
  font-size: 14px;
}

.warning-text {
  font-size: 11px;
  color: #fca5a5;
}

.messages-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.message {
  display: flex;
  gap: 10px;
  padding: 12px;
  border-radius: 12px;
  max-width: 85%;
}

.message.user {
  align-self: flex-end;
  background: rgba(99, 102, 241, 0.2);
  border: 1px solid rgba(99, 102, 241, 0.3);
  margin-left: auto;
}

.message.assistant {
  align-self: flex-start;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.message-avatar {
  font-size: 18px;
  flex-shrink: 0;
}

.message-content {
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-main);
}

.message-content.loading {
  color: var(--text-muted);
  font-style: italic;
}

.retrieval-section {
  width: 100%;
  max-width: 100%;
  margin-top: 8px;
}
</style>