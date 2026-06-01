<script setup>
import { computed } from 'vue'

const props = defineProps({
  stage: {
    type: Object,
    default: null,
  },
  technicalView: {
    type: Boolean,
    default: false,
  },
})

const details = computed(() => props.stage?.details || {})
const technical = computed(() => props.stage?.technical || {})
const results = computed(() => props.stage?.results || [])

const formatJson = (value) => JSON.stringify(value, null, 2)
</script>

<template>
  <section class="stage-detail" aria-live="polite">
    <div v-if="!stage" class="empty-state">
      <span class="eyebrow">Ready</span>
      <h2>Run a demo trace</h2>
      <p>Enter a question to show how retrieval and generation work together.</p>
    </div>

    <template v-else>
      <div class="stage-heading">
        <span class="eyebrow">{{ stage.status }}</span>
        <h2>{{ stage.title }}</h2>
        <p>{{ stage.summary }}</p>
      </div>

      <div v-if="Object.keys(details).length" class="detail-block">
        <h3>What happened</h3>
        <pre>{{ formatJson(details) }}</pre>
      </div>

      <div v-if="results.length" class="result-list">
        <h3>Stage Results</h3>
        <div v-for="item in results" :key="`${stage.id}-${item.rank || item.id || item.source}`" class="result-item">
          <div class="result-meta">
            <span v-if="item.rank">Rank {{ item.rank }}</span>
            <span v-if="item.source">{{ item.source }}</span>
            <span v-if="item.page">Page {{ item.page }}</span>
            <span v-if="item.score !== undefined">Score {{ item.score }}</span>
          </div>
          <p>{{ item.preview || item.text || item.id }}</p>
        </div>
      </div>

      <div v-if="technicalView && Object.keys(technical).length" class="detail-block technical-block">
        <h3>Technical Data</h3>
        <pre>{{ formatJson(technical) }}</pre>
      </div>

      <div v-if="stage.error" class="error-block">
        <h3>Error</h3>
        <p>{{ stage.error }}</p>
      </div>
    </template>
  </section>
</template>

<style scoped>
.stage-detail {
  min-width: 0;
  padding: 24px;
  overflow-y: auto;
}

.empty-state,
.stage-heading,
.detail-block,
.result-list,
.error-block {
  margin-bottom: 18px;
}

.eyebrow {
  display: block;
  margin-bottom: 6px;
  color: var(--primary);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

h2,
h3,
p {
  margin: 0;
}

h2 {
  margin-bottom: 8px;
  font-size: 28px;
  color: var(--on-surface);
}

h3 {
  margin-bottom: 10px;
  font-size: 14px;
  color: var(--on-surface);
}

p {
  color: var(--on-surface-variant);
  line-height: 1.6;
}

pre {
  margin: 0;
  padding: 14px;
  border-radius: 8px;
  background: var(--surface-container-lowest);
  color: var(--on-surface);
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.5;
}

.result-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.result-item {
  padding: 12px;
  border-radius: 8px;
  background: var(--surface-container-low);
  border: 1px solid rgba(69, 70, 83, 0.22);
}

.result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
  color: var(--primary);
  font-size: 11px;
  font-weight: 700;
}

.technical-block pre {
  border: 1px solid rgba(129, 140, 248, 0.24);
}

.error-block {
  padding: 14px;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.28);
}
</style>
