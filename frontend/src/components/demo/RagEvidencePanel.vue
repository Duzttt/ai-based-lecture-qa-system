<script setup>
defineProps({
  chunks: {
    type: Array,
    default: () => [],
  },
  contextPreview: {
    type: String,
    default: '',
  },
  answer: {
    type: String,
    default: '',
  },
  technicalView: {
    type: Boolean,
    default: false,
  },
})
</script>

<template>
  <aside class="evidence-panel" aria-label="Evidence panel">
    <section class="panel-section">
      <span class="eyebrow">Evidence</span>
      <h2>Retrieved Chunks</h2>
      <p v-if="chunks.length === 0" class="muted">No chunks retrieved yet.</p>

      <div v-for="(chunk, index) in chunks" :key="`${chunk.source}-${chunk.page}-${index}`" class="chunk-card">
        <div class="chunk-meta">
          <span>#{{ index + 1 }}</span>
          <span>{{ chunk.source }}</span>
          <span v-if="chunk.page">Page {{ chunk.page }}</span>
        </div>
        <p>{{ chunk.preview || chunk.text }}</p>
        <div v-if="technicalView" class="technical-row">
          <span>Score {{ chunk.score }}</span>
          <span>Distance {{ chunk.distance }}</span>
        </div>
      </div>
    </section>

    <section class="panel-section">
      <span class="eyebrow">Context</span>
      <h2>Prompt Context</h2>
      <pre>{{ contextPreview || 'Context will appear after retrieval completes.' }}</pre>
    </section>

    <section class="panel-section">
      <span class="eyebrow">Answer</span>
      <h2>Final Answer</h2>
      <p class="answer-text">{{ answer || 'The answer will appear after generation completes.' }}</p>
    </section>
  </aside>
</template>

<style scoped>
.evidence-panel {
  min-width: 300px;
  max-width: 360px;
  padding: 18px;
  background: var(--surface-container-low);
  border-left: 1px solid rgba(69, 70, 83, 0.2);
  overflow-y: auto;
}

.panel-section {
  margin-bottom: 22px;
}

.eyebrow {
  display: block;
  margin-bottom: 4px;
  color: var(--primary);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

h2,
p {
  margin: 0;
}

h2 {
  margin-bottom: 10px;
  font-size: 15px;
  color: var(--on-surface);
}

.muted,
.answer-text,
.chunk-card p {
  color: var(--on-surface-variant);
  font-size: 13px;
  line-height: 1.6;
}

.chunk-card {
  margin-bottom: 10px;
  padding: 12px;
  border-radius: 8px;
  background: var(--surface-container);
  border: 1px solid rgba(69, 70, 83, 0.24);
}

.chunk-meta,
.technical-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
  color: var(--primary);
  font-size: 11px;
  font-weight: 700;
}

.technical-row {
  margin-top: 10px;
  margin-bottom: 0;
  color: var(--tertiary);
}

pre {
  margin: 0;
  max-height: 220px;
  overflow-y: auto;
  padding: 12px;
  border-radius: 8px;
  background: var(--surface-container-lowest);
  color: var(--on-surface-variant);
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.5;
}
</style>
