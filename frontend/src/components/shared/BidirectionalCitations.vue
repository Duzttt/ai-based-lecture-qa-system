<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false,
  },
  source: {
    type: String,
    default: '',
  },
  page: {
    type: Number,
    default: null,
  },
  text: {
    type: String,
    default: '',
  },
  citations: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['close', 'navigate-to-message'])

const searchQuery = ref('')

const filteredCitations = computed(() => {
  if (!props.citations || props.citations.length === 0) {
    return []
  }

  if (!searchQuery.value.trim()) {
    return props.citations
  }

  const query = searchQuery.value.toLowerCase()
  return props.citations.filter(cit =>
    cit.query?.toLowerCase().includes(query) ||
    cit.answer?.toLowerCase().includes(query)
  )
})

const navigateToMessage = (messageId) => {
  emit('navigate-to-message', messageId)
  emit('close')
}
</script>

<template>
  <div v-if="show" class="bidirectional-panel" :class="{ visible: show }">
    <div class="bidirectional-header">
      <span class="bidirectional-title">
        <span>🔗</span>
        Citations to this text
      </span>
      <button class="bidirectional-close" @click="$emit('close')">✕</button>
    </div>

    <div class="bidirectional-source-info" v-if="source || text">
      <div class="source-file">
        <span class="file-icon">📄</span>
        <span class="file-name">{{ source?.split('/').pop() || 'Unknown' }}</span>
      </div>
      <div class="source-page" v-if="page">Page {{ page }}</div>
    </div>

    <div class="bidirectional-search" v-if="citations.length > 1">
      <input
        v-model="searchQuery"
        type="text"
        class="search-input"
        placeholder="Search citations..."
      />
    </div>

    <div class="bidirectional-body" id="bidirectionalBody">
      <div v-if="filteredCitations.length === 0" class="bidirectional-empty">
        <span class="empty-icon">📭</span>
        <span v-if="citations.length === 0">
          No other answers cite this text yet.
        </span>
        <span v-else>
          No citations match your search.
        </span>
      </div>

      <div
        v-for="(cit, idx) in filteredCitations"
        :key="cit.messageId || idx"
        class="bidirectional-item"
        @click="navigateToMessage(cit.messageId)"
      >
        <div class="bidirectional-query">
          <span class="query-label">Q:</span>
          {{ cit.query || '...' }}
        </div>
        <div class="bidirectional-answer">
          <span class="answer-label">A:</span>
          {{ (cit.answer || '').substring(0, 150) }}{{ (cit.answer || '').length > 150 ? '...' : '' }}
        </div>
        <div class="bidirectional-meta">
          <span class="message-time" v-if="cit.timestamp">{{ cit.timestamp }}</span>
          <span class="click-hint">Click to view</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bidirectional-panel {
  position: fixed;
  bottom: 20px;
  right: 20px;
  width: 380px;
  max-height: 450px;
  background: rgba(15, 23, 42, 0.98);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(99, 102, 241, 0.4);
  border-radius: 16px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.6);
  z-index: 4500;
  overflow: hidden;
  display: none;
  flex-direction: column;
}

.bidirectional-panel.visible {
  display: flex;
}

.bidirectional-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: rgba(99, 102, 241, 0.15);
  border-bottom: 1px solid rgba(99, 102, 241, 0.2);
  flex-shrink: 0;
}

.bidirectional-title {
  font-size: 13px;
  font-weight: 600;
  color: white;
  display: flex;
  align-items: center;
  gap: 8px;
}

.bidirectional-close {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  transition: all 0.2s;
}

.bidirectional-close:hover {
  background: rgba(255, 255, 255, 0.1);
  color: white;
}

.bidirectional-source-info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: rgba(0, 0, 0, 0.2);
  border-bottom: 1px solid rgba(55, 65, 81, 0.5);
  font-size: 11px;
}

.source-file {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-main);
  flex: 1;
  overflow: hidden;
}

.file-icon {
  font-size: 14px;
}

.file-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.source-page {
  color: var(--accent);
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.15);
}

.bidirectional-search {
  padding: 8px 16px;
  background: rgba(0, 0, 0, 0.15);
  border-bottom: 1px solid rgba(55, 65, 81, 0.5);
}

.search-input {
  width: 100%;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid rgba(55, 65, 81, 0.8);
  background: rgba(2, 6, 23, 0.8);
  color: var(--text-main);
  font-size: 12px;
  outline: none;
  transition: all 0.2s;
}

.search-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.bidirectional-body {
  flex: 1;
  padding: 12px 16px;
  max-height: 320px;
  overflow-y: auto;
}

.bidirectional-item {
  padding: 12px;
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid rgba(55, 65, 81, 0.5);
  border-radius: 10px;
  margin-bottom: 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.bidirectional-item:hover {
  border-color: var(--accent);
  background: rgba(99, 102, 241, 0.1);
  transform: translateX(2px);
}

.bidirectional-item:last-child {
  margin-bottom: 0;
}

.bidirectional-query {
  font-size: 12px;
  color: var(--text-main);
  margin-bottom: 6px;
  line-height: 1.5;
}

.query-label {
  font-weight: 600;
  color: var(--accent);
  margin-right: 4px;
}

.bidirectional-answer {
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.answer-label {
  font-weight: 600;
  color: #22c55e;
  margin-right: 4px;
}

.bidirectional-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  font-size: 10px;
}

.message-time {
  color: var(--text-muted);
}

.click-hint {
  color: var(--accent);
  font-weight: 500;
}

.bidirectional-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--text-muted);
  gap: 12px;
  text-align: center;
}

.empty-icon {
  font-size: 32px;
}

/* Scrollbar styling */
.bidirectional-body::-webkit-scrollbar {
  width: 6px;
}

.bidirectional-body::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 3px;
}

.bidirectional-body::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
}

.bidirectional-body::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}
</style>
