<script setup>
import { ref } from 'vue'

const props = defineProps({
  isLoading: Boolean
})

const emit = defineEmits(['send'])

const question = ref('')

const sendMessage = () => {
  if (!question.value.trim()) return
  emit('send', question.value)
  question.value = ''
}
</script>

<template>
  <div class="chat-input-wrap">
    <label class="sr-only" for="chat-question-input">Your question</label>
    <button
      type="button"
      class="attach-btn"
      aria-label="Attach file (coming soon)"
      disabled
    >
      <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M16.5 6v11.5c0 2.21-1.79 4-4 4s-4-1.79-4-4V5c0-1.38 1.12-2.5 2.5-2.5s2.5 1.12 2.5 2.5v10.5c0 .55-.45 1-1 1s-1-.45-1-1V6H10v9.5c0 1.38 1.12 2.5 2.5 2.5s2.5-1.12 2.5-2.5V5c0-2.21-1.79-4-4-4S7 2.79 7 5v12.5c0 3.04 2.46 5.5 5.5 5.5s5.5-2.46 5.5-5.5V6h-1.5z"/></svg>
    </button>
    <input
      id="chat-question-input"
      v-model="question"
      @keydown.enter.prevent="sendMessage"
      type="text"
      class="chat-input"
      name="question"
      autocomplete="off"
      placeholder="Ask a question…"
      :disabled="isLoading"
    />
    <button
      type="button"
      class="chat-send-btn"
      aria-label="Send message"
      @click="sendMessage"
      :disabled="isLoading || !question.trim()"
    >
      <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
    </button>
  </div>
</template>

<style scoped>
.chat-input-wrap {
  padding: 12px 16px 16px;
  display: flex;
  gap: 10px;
  align-items: center;
  background: var(--surface-container);
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.attach-btn {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  border: none;
  background: var(--surface-container-high);
  color: var(--on-surface-variant);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background-color 0.2s, color 0.2s;
  flex-shrink: 0;
}

.attach-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.attach-btn:focus-visible {
  outline: 2px solid var(--primary-container);
  outline-offset: 2px;
}

.attach-btn svg {
  width: 18px;
  height: 18px;
}

.attach-btn:hover {
  background: var(--surface-container-highest);
  color: var(--on-surface);
}

.chat-input {
  flex: 1;
  padding: 10px 16px;
  border-radius: 10px;
  border: 1px solid rgba(69, 70, 83, 0.15);
  background: var(--surface-container-lowest);
  color: var(--on-surface);
  font-family: var(--font-body);
  font-size: 13px;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.chat-input:focus {
  outline: none;
}

.chat-input:focus-visible {
  outline: none;
  border-color: var(--primary-container);
  box-shadow: 0 0 0 2px rgba(129, 140, 248, 0.35);
}

.chat-input::placeholder {
  color: var(--on-surface-variant);
  opacity: 0.5;
}

.chat-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chat-send-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-container) 100%);
  color: var(--on-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s, opacity 0.2s;
  flex-shrink: 0;
}

.chat-send-btn:focus-visible {
  outline: 2px solid var(--primary);
  outline-offset: 2px;
}

.chat-send-btn svg {
  width: 18px;
  height: 18px;
}

.chat-send-btn:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 4px 16px rgba(129, 140, 248, 0.3);
}

.chat-send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  transform: none;
}
</style>
