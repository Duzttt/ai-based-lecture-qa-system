<script setup>
import { ref } from 'vue'

const props = defineProps({
  isLoading: Boolean
})

const emit = defineEmits(['send'])

const question = ref('')

const handleKeyPress = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

const sendMessage = () => {
  if (!question.value.trim()) return
  emit('send', question.value)
  question.value = ''
}
</script>

<template>
  <div class="chat-input-wrap">
    <input
      v-model="question"
      @keydown.enter.prevent="sendMessage"
      type="text"
      class="chat-input"
      placeholder="Ask a question..."
      :disabled="isLoading"
    />
    <button
      class="chat-send-btn"
      @click="sendMessage"
      :disabled="isLoading || !question.trim()"
    >
      ➤
    </button>
  </div>
</template>

<style scoped>
.chat-input-wrap {
  padding: 10px 14px 12px;
  border-top: 1px solid rgba(31, 41, 55, 0.9);
  display: flex;
  gap: 8px;
  align-items: center;
  position: sticky;
  bottom: 0;
  z-index: 5;
  background: rgba(15, 23, 42, 0.85);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
}

.chat-input {
  flex: 1;
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid rgba(55, 65, 81, 0.9);
  background: #020617;
  color: var(--text-main);
  font-size: 13px;
  outline: none;
  transition: all 0.2s;
}

.chat-input:focus {
  border-color: var(--accent);
}

.chat-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chat-send-btn {
  width: 32px;
  height: 32px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: linear-gradient(
    145deg,
    rgba(99, 102, 241, 0.8) 0%,
    rgba(139, 92, 246, 0.9) 100%
  );
  color: #f9fafb;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 14px;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  box-shadow:
    0 5px 15px -5px rgba(99, 102, 241, 0.3),
    inset 0 1px 2px rgba(255, 255, 255, 0.3);
  transition: all 0.2s ease;
}

.chat-send-btn:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow:
    0 8px 20px -5px rgba(99, 102, 241, 0.5),
    inset 0 1px 3px rgba(255, 255, 255, 0.4);
}

.chat-send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}
</style>