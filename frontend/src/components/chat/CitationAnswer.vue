<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  /**
   * Array of sentences with citations:
   * [{ text: "...", citations: [1, 2] }, ...]
   */
  sentences: {
    type: Array,
    default: () => [],
  },
  /**
   * Sources map by chunk ID:
   * { "1": { file: "lecture.pdf", page: 24 }, ... }
   */
  sources: {
    type: Object,
    default: () => ({}),
  },
  /**
   * Whether to show the tooltip on hover
   */
  showTooltip: {
    type: Boolean,
    default: true,
  },
})

const activeTooltip = ref(null)
const tooltipPosition = ref({ x: 0, y: 0 })

/**
 * Get source info for a citation ID
 */
const getSourceInfo = (citationId) => {
  const idStr = String(citationId)
  return props.sources[idStr] || null
}

/**
 * Get multiple source infos for citation array
 */
const getSourceInfos = (citationIds) => {
  return citationIds
    .map((id) => ({ id, info: getSourceInfo(id) }))
    .filter((item) => item.info !== null)
}

/**
 * Check if a sentence has citations
 */
const hasCitations = (sentence) => {
  return sentence.citations && sentence.citations.length > 0
}

/**
 * Format file name for display (just the base name)
 */
const formatFileName = (fileName) => {
  if (!fileName) return 'Unknown'
  const parts = fileName.split('/')
  return parts[parts.length - 1]
}

/**
 * Handle mouse enter on a cited sentence
 */
const handleMouseEnter = (event, sentence, index) => {
  if (!props.showTooltip || !hasCitations(sentence)) return

  const rect = event.target.getBoundingClientRect()
  tooltipPosition.value = {
    x: rect.left + rect.width / 2,
    y: rect.bottom + 8,
  }
  activeTooltip.value = index
}

/**
 * Handle mouse leave on a cited sentence
 */
const handleMouseLeave = () => {
  activeTooltip.value = null
}

/**
 * Get citation label for a sentence (e.g., [1, 2])
 */
const getCitationLabel = (citations) => {
  if (!citations || citations.length === 0) return ''
  return `[${citations.join(', ')}]`
}
</script>

<template>
  <div class="citation-answer">
    <p class="answer-paragraph">
      <span
        v-for="(sentence, idx) in sentences"
        :key="idx"
        class="sentence"
        :class="{ 'has-citations': hasCitations(sentence) }"
        @mouseenter="handleMouseEnter($event, sentence, idx)"
        @mouseleave="handleMouseLeave"
      >
        {{ sentence.text }}
        <sup v-if="hasCitations(sentence)" class="citation-marker">
          {{ getCitationLabel(sentence.citations) }}
        </sup>
      </span>
    </p>

    <!-- Tooltip -->
    <Teleport to="body">
      <transition name="tooltip-fade">
        <div
          v-if="showTooltip && activeTooltip !== null && sentences[activeTooltip]"
          class="citation-tooltip"
          :style="{
            left: `${tooltipPosition.x}px`,
            top: `${tooltipPosition.y}px`,
          }"
        >
          <div class="tooltip-header">
            <span class="tooltip-icon">📚</span>
            <span class="tooltip-title">
              {{ sentences[activeTooltip].citations.length === 1 ? 'Source' : 'Sources' }}
            </span>
          </div>
          <div class="tooltip-content">
            <div
              v-for="{ id, info } in getSourceInfos(sentences[activeTooltip].citations)"
              :key="id"
              class="tooltip-source-item"
            >
              <span class="source-file" :title="info.file">
                {{ formatFileName(info.file) }}
              </span>
              <span v-if="info.page !== null && info.page !== undefined" class="source-page">
                (p. {{ info.page }})
              </span>
            </div>
          </div>
        </div>
      </transition>
    </Teleport>
  </div>
</template>

<style scoped>
.citation-answer {
  width: 100%;
}

.answer-paragraph {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-main);
  margin: 0;
}

.sentence {
  transition: all 0.2s ease;
  padding: 1px 0;
}

.sentence.has-citations {
  text-decoration: underline;
  text-decoration-style: dotted;
  text-decoration-thickness: 1px;
  text-underline-offset: 2px;
  cursor: pointer;
  border-bottom: 1px dotted rgba(99, 102, 241, 0.5);
}

.sentence.has-citations:hover {
  background: rgba(99, 102, 241, 0.1);
  border-radius: 2px;
  text-decoration-style: solid;
  border-bottom-style: solid;
}

.citation-marker {
  font-size: 10px;
  color: var(--accent);
  font-weight: 600;
  margin-left: 2px;
  vertical-align: super;
}

/* Tooltip Styles */
.citation-tooltip {
  position: fixed;
  min-width: 200px;
  max-width: 320px;
  background: rgba(15, 23, 42, 0.98);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(99, 102, 241, 0.4);
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.6);
  z-index: 10000;
  overflow: hidden;
  pointer-events: none;
  transform: translateX(-50%);
  animation: tooltip-appear 0.15s ease-out;
}

@keyframes tooltip-appear {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(-5px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}

.tooltip-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: rgba(99, 102, 241, 0.15);
  border-bottom: 1px solid rgba(99, 102, 241, 0.2);
}

.tooltip-icon {
  font-size: 14px;
}

.tooltip-title {
  font-size: 11px;
  font-weight: 600;
  color: white;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.tooltip-content {
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 200px;
  overflow-y: auto;
}

.tooltip-source-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-main);
  padding: 4px 6px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
}

.source-file {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 500;
}

.source-page {
  color: var(--accent);
  font-weight: 600;
  font-size: 10px;
  white-space: nowrap;
}

/* Tooltip fade transition */
.tooltip-fade-enter-active,
.tooltip-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.tooltip-fade-enter-from,
.tooltip-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-5px);
}

/* Scrollbar for tooltip content */
.tooltip-content::-webkit-scrollbar {
  width: 4px;
}

.tooltip-content::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 2px;
}

.tooltip-content::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 2px;
}

.tooltip-content::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}
</style>
