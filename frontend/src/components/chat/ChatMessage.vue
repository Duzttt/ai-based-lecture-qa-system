<script setup>
import { ref } from 'vue'
import CitationAnswer from './CitationAnswer.vue'

const props = defineProps({
  message: Object
})

const emit = defineEmits(['chunk-hover', 'chunk-click', 'chunk-rightclick'])

const showReasoning = ref(false)

const toggleReasoning = () => {
  showReasoning.value = !showReasoning.value
}

const getMessageCitationTitle = (msg) => {
  if (!msg || msg.role !== 'assistant' || !msg.chunks || !msg.chunks.length) {
    return ''
  }
  const sources = Array.from(
    new Set(
      msg.chunks
        .map((c) => c.source)
        .filter((s) => typeof s === 'string' && s.trim()),
    ),
  )
  if (!sources.length) return ''
  return `Supported by: ${sources.join(', ')}`
}
</script>

<template>
  <div class="message" :class="message.role">
    <div class="message-avatar" aria-hidden="true">{{ message.role === 'user' ? '👤' : '🤖' }}</div>
    <span class="sr-only">{{ message.role === 'user' ? 'You' : 'Assistant' }}</span>
    <div
      class="message-content"
      :class="{
        'has-citations': message.role === 'assistant' && message.chunks && message.chunks.length > 0
      }"
      :title="getMessageCitationTitle(message)"
    >
      <!-- Reasoning/Thinking Section (Collapsible) -->
      <div v-if="message.reasoning" class="reasoning-section">
        <button 
          class="reasoning-toggle" 
          @click="toggleReasoning"
          :aria-expanded="showReasoning"
          :aria-controls="`reasoning-content-${message.id}`"
        >
          <span class="reasoning-icon">
            {{ showReasoning ? '▼' : '▶' }}
          </span>
          <span class="reasoning-label">
            {{ showReasoning ? 'Hide' : 'Show' }} thinking process
          </span>
          <span class="reasoning-badge">
            🧠 Reasoning
          </span>
        </button>
        
        <transition name="reasoning-expand">
          <div v-show="showReasoning" :id="`reasoning-content-${message.id}`" class="reasoning-content">
            <div class="reasoning-text">{{ message.reasoning }}</div>
          </div>
        </transition>
      </div>

      <!-- Answer Section -->
      <CitationAnswer
        v-if="message.role === 'assistant' && message.sentences && message.sentences.length > 0"
        :sentences="message.sentences"
        :sources="message.sources"
        :show-tooltip="true"
      />
      <template v-else>
        {{ message.content }}
      </template>
    </div>
  </div>
</template>

<style scoped>
.message {
  position: relative;
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

.message-avatar {
  font-size: 18px;
  flex-shrink: 0;
}

.message-content {
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-main);
  flex: 1;
  min-width: 0;
}

.message-content.has-citations {
  position: relative;
}

/* Reasoning/Thinking Section */
.reasoning-section {
  margin-bottom: 12px;
  border: 1px solid rgba(168, 85, 247, 0.3);
  border-radius: 8px;
  background: rgba(168, 85, 247, 0.05);
  overflow: hidden;
}

.reasoning-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: rgba(168, 85, 247, 0.1);
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-main);
  transition: all 0.2s ease;
  text-align: left;
}

.reasoning-toggle:hover {
  background: rgba(168, 85, 247, 0.15);
}

.reasoning-toggle:active {
  background: rgba(168, 85, 247, 0.2);
}

.reasoning-icon {
  font-size: 10px;
  color: rgba(168, 85, 247, 0.8);
  transition: transform 0.2s ease;
  flex-shrink: 0;
}

.reasoning-label {
  flex: 1;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.7);
}

.reasoning-badge {
  padding: 2px 8px;
  background: rgba(168, 85, 247, 0.2);
  border: 1px solid rgba(168, 85, 247, 0.3);
  border-radius: 12px;
  font-size: 10px;
  font-weight: 600;
  color: rgba(168, 85, 247, 0.9);
  flex-shrink: 0;
}

.reasoning-content {
  padding: 12px;
  background: rgba(15, 23, 42, 0.3);
  border-top: 1px solid rgba(168, 85, 247, 0.2);
}

.reasoning-text {
  font-size: 12px;
  line-height: 1.6;
  color: rgba(255, 255, 255, 0.6);
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: 'Courier New', Courier, monospace;
  padding: 8px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
  border-left: 3px solid rgba(168, 85, 247, 0.4);
}

/* Reasoning expand animation */
.reasoning-expand-enter-active,
.reasoning-expand-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}

.reasoning-expand-enter-from,
.reasoning-expand-leave-to {
  opacity: 0;
  max-height: 0;
}

.reasoning-expand-enter-to,
.reasoning-expand-leave-from {
  opacity: 1;
  max-height: 2000px;
}
</style>
