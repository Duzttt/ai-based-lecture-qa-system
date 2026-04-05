<script setup>
import CitationAnswer from './CitationAnswer.vue'

const props = defineProps({
  message: Object
})

const emit = defineEmits(['chunk-hover', 'chunk-click', 'chunk-rightclick'])

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
}

.message-content.has-citations {
  position: relative;
}
</style>
