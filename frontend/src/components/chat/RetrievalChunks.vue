<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  chunks: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['chunk-hover', 'chunk-click', 'chunk-rightclick'])

const isOpen = ref(false)
const expandedChunks = ref(new Set())
const showAllChunks = ref(false)
const hoveredChunk = ref(null)
const tooltipPosition = ref({ x: 0, y: 0 })

const SIMILARITY_THRESHOLD = 0.6

const filteredChunks = computed(() => {
  if (!props.chunks || props.chunks.length === 0) {
    return []
  }

  if (showAllChunks.value) {
    return props.chunks
  }

  const strongMatches = props.chunks.filter(
    (chunk) => (chunk.score ?? 0) >= SIMILARITY_THRESHOLD,
  )

  if (strongMatches.length === 0) {
    return props.chunks
  }

  return strongMatches
})

const getScoreColor = (score) => {
  if (score >= 0.8) return '#22c55e'
  if (score >= 0.5) return '#eab308'
  return '#6b7280'
}

const getScoreColorClass = (score) => {
  if (score >= 0.8) return 'score-high'
  if (score >= 0.5) return 'score-medium'
  return 'score-low'
}

const toggleExpand = (index) => {
  const newSet = new Set(expandedChunks.value)
  if (newSet.has(index)) {
    newSet.delete(index)
  } else {
    newSet.add(index)
  }
  expandedChunks.value = newSet
}

const isExpanded = (index) => {
  return expandedChunks.value.has(index)
}

const handleChunkHover = (chunk, event) => {
  hoveredChunk.value = chunk
  const rect = event.target.getBoundingClientRect()
  tooltipPosition.value = {
    x: rect.left,
    y: rect.bottom + 10
  }
  emit('chunk-hover', chunk)
}

const handleChunkLeave = () => {
  hoveredChunk.value = null
}

const handleChunkClick = (chunk) => {
  emit('chunk-click', chunk)
}

const handleChunkRightClick = (event, chunk) => {
  emit('chunk-rightclick', event, chunk)
}
</script>

<template>
  <div v-if="loading" class="retrieval-loading">
    <div class="loading-spinner"></div>
    <span>Searching knowledge base...</span>
  </div>
  
  <div v-else-if="filteredChunks.length > 0" class="retrieval-chunks">
    <div class="retrieval-header">
      <div class="retrieval-meta">
        <span class="retrieval-title">📚 Retrieved Context</span>
        <span class="retrieval-count">{{ filteredChunks.length }} of {{ chunks.length }} chunks</span>
      </div>

      <div class="retrieval-actions">
        <button
          v-if="chunks.length > filteredChunks.length"
          class="show-all-btn"
          @click.stop="showAllChunks = !showAllChunks"
        >
          {{ showAllChunks ? 'Show Relevant Only' : `Show All (${chunks.length})` }}
        </button>
        <button class="collapse-btn" @click.stop="isOpen = !isOpen">
          <span class="collapse-icon">{{ isOpen ? '▼' : '▶' }}</span>
          <span class="collapse-label">{{ isOpen ? 'Hide' : 'Show' }}</span>
        </button>
      </div>
    </div>
    
    <div v-if="isOpen" class="chunks-scroll">
      <div class="chunks-grid">
        <div
          v-for="(chunk, index) in filteredChunks"
          :key="index"
          class="chunk-card"
          :class="getScoreColorClass(chunk.score)"
          @mouseenter="handleChunkHover(chunk, $event)"
          @mouseleave="handleChunkLeave"
          @click="handleChunkClick(chunk)"
          @contextmenu="handleChunkRightClick($event, chunk)"
        >
          <div class="chunk-header">
            <div class="chunk-score">
              <div
                class="score-badge"
                :style="{ backgroundColor: getScoreColor(chunk.score) }"
              >
                {{ Math.round(chunk.score * 100) }}%
              </div>
            </div>
            <div class="chunk-source">
              <span class="source-name">{{ chunk.source }}</span>
              <span v-if="chunk.page" class="source-page">Page {{ chunk.page }}</span>
            </div>
            <button class="expand-btn" @click.stop="toggleExpand(index)">
              {{ isExpanded(index) ? '▼' : '▶' }}
            </button>
          </div>

          <div class="chunk-progress">
            <div
              class="progress-bar"
              :style="{
                width: chunk.score * 100 + '%',
                background: `linear-gradient(90deg, ${getScoreColor(chunk.score)} 0%, ${getScoreColor(chunk.score)}80 100%)`,
              }"
            ></div>
          </div>

          <div class="chunk-content">
            <p class="chunk-preview">
              {{ isExpanded(index) ? chunk.text : chunk.preview }}
            </p>
          </div>

          <div v-if="chunk.text.length > 100" class="chunk-footer">
            <span class="char-count">
              {{ isExpanded(index) ? chunk.text.length : 100 }} / {{ chunk.text.length }} chars
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Chunk Preview Tooltip -->
    <div
      v-if="hoveredChunk"
      class="chunk-tooltip"
      :style="{ left: tooltipPosition.x + 'px', top: tooltipPosition.y + 'px' }"
    >
      <div class="chunk-tooltip-header">
        <span class="tooltip-source">📄 {{ hoveredChunk.source }}</span>
        <span v-if="hoveredChunk.page" class="tooltip-page">· Page {{ hoveredChunk.page }}</span>
        <span class="tooltip-score" :style="{ color: getScoreColor(hoveredChunk.score) }">
          {{ Math.round(hoveredChunk.score * 100) }}% match
        </span>
      </div>
      <div class="chunk-tooltip-body">
        {{ hoveredChunk.text }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.retrieval-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px 20px;
  color: var(--text-muted);
  font-size: 13px;
}

.loading-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(99, 102, 241, 0.2);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.retrieval-chunks {
  margin-top: 16px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.02);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.retrieval-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.retrieval-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.retrieval-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.retrieval-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
}

.retrieval-count {
  font-size: 11px;
  color: var(--text-muted);
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
}

.show-all-btn {
  padding: 4px 12px;
  font-size: 11px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.2s;
}

.show-all-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-main);
  border-color: rgba(255, 255, 255, 0.2);
}

.collapse-btn {
  padding: 4px 10px;
  font-size: 11px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-muted);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: all 0.2s;
}

.collapse-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-main);
  border-color: rgba(255, 255, 255, 0.2);
}

.collapse-icon {
  font-size: 10px;
  line-height: 1;
}

.chunks-scroll {
  max-height: 320px;
  overflow: auto;
  padding-right: 2px;
}

.chunks-scroll::-webkit-scrollbar {
  width: 8px;
}

.chunks-scroll::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 6px;
}

.chunks-scroll::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.18);
  border-radius: 6px;
}

.chunks-scroll::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.28);
}

.chunks-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.chunk-card {
  position: relative;
  padding: 12px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  cursor: pointer;
  transition: all 0.2s ease;
  overflow: hidden;
}

.chunk-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, var(--accent), #a855f7);
  opacity: 0;
  transition: opacity 0.2s;
}

.chunk-card:hover {
  transform: translateY(-2px);
  border-color: rgba(99, 102, 241, 0.3);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.3);
}

.chunk-card:hover::before {
  opacity: 1;
}

.chunk-card.score-high {
  border-left: 3px solid #22c55e;
}

.chunk-card.score-medium {
  border-left: 3px solid #eab308;
}

.chunk-card.score-low {
  border-left: 3px solid #6b7280;
}

.chunk-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.chunk-score {
  flex-shrink: 0;
}

.score-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 600;
  color: white;
  border-radius: 999px;
  min-width: 42px;
}

.chunk-source {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.source-name {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-main);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.source-page {
  font-size: 10px;
  color: var(--text-muted);
}

.expand-btn {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  transition: all 0.2s;
  flex-shrink: 0;
}

.expand-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-main);
}

.chunk-progress {
  height: 3px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 10px;
}

.progress-bar {
  height: 100%;
  transition: width 0.5s ease;
  border-radius: 2px;
}

.chunk-content {
  margin-bottom: 8px;
}

.chunk-preview {
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-main);
  margin: 0;
  padding: 8px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.chunk-preview::-webkit-scrollbar {
  width: 6px;
}

.chunk-preview::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 3px;
}

.chunk-preview::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
}

.chunk-preview::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}

.chunk-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 6px;
}

.char-count {
  font-size: 10px;
  color: var(--text-muted);
  padding: 2px 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.03);
}

/* Chunk Tooltip */
.chunk-tooltip {
  position: fixed;
  z-index: 5000;
  min-width: 300px;
  max-width: 450px;
  background: rgba(15, 23, 42, 0.98);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.6);
  padding: 12px;
  pointer-events: none;
  animation: tooltipFadeIn 0.2s ease;
}

@keyframes tooltipFadeIn {
  from {
    opacity: 0;
    transform: translateY(5px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.chunk-tooltip-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.tooltip-source {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-main);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tooltip-page {
  font-size: 10px;
  color: var(--text-muted);
}

.tooltip-score {
  margin-left: auto;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
}

.chunk-tooltip-body {
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-main);
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.chunk-tooltip-body::-webkit-scrollbar {
  width: 6px;
}

.chunk-tooltip-body::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 3px;
}

.chunk-tooltip-body::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
}

@media (max-width: 768px) {
  .chunks-grid {
    grid-template-columns: 1fr;
  }

  .retrieval-header {
    flex-wrap: wrap;
  }

  .show-all-btn {
    width: 100%;
    margin-top: 8px;
  }

  .chunk-tooltip {
    min-width: 250px;
    max-width: 90vw;
  }
}
</style>
