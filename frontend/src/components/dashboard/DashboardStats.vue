<script setup>
const props = defineProps({
  stats: Object,
  metrics: Object
})

const formatSize = (kb) => {
  if (kb < 1024) return `${kb.toFixed(1)} KB`
  return `${(kb / 1024).toFixed(2)} MB`
}
</script>

<template>
  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-icon doc">📄</div>
      <div class="stat-content">
        <div class="stat-value">{{ stats.documents.total }}</div>
        <div class="stat-label">Documents</div>
        <div class="stat-sub">{{ stats.documents.total_pages }} pages · {{ stats.documents.total_chunks }} chunks</div>
      </div>
    </div>

    <div class="stat-card">
      <div class="stat-icon vector">📏</div>
      <div class="stat-content">
        <div class="stat-value">{{ stats.vectors.total_vectors }}</div>
        <div class="stat-label">Vectors</div>
        <div class="stat-sub">{{ stats.vectors.index_type }} · {{ stats.vectors.dimension }}D</div>
      </div>
    </div>

    <div class="stat-card">
      <div class="stat-icon perf">⚡</div>
      <div class="stat-content">
        <div class="stat-value">{{ metrics.retrieval_time_ms.toFixed(1) }}ms</div>
        <div class="stat-label">Retrieval Time</div>
        <div class="stat-sub">Embedding: {{ metrics.embedding_time_ms.toFixed(1) }}ms</div>
      </div>
    </div>

    <div class="stat-card">
      <div class="stat-icon storage">💾</div>
      <div class="stat-content">
        <div class="stat-value">{{ formatSize(stats.storage.faiss_index_size_kb) }}</div>
        <div class="stat-label">Index Size</div>
        <div class="stat-sub">Docs: {{ formatSize(stats.storage.documents_size_kb) }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  gap: 14px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  transition: all 0.2s;
}

.stat-card:hover {
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(99, 102, 241, 0.3);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  flex-shrink: 0;
}

.stat-icon.doc { background: rgba(34, 197, 94, 0.15); }
.stat-icon.vector { background: rgba(99, 102, 241, 0.15); }
.stat-icon.perf { background: rgba(251, 191, 36, 0.15); }
.stat-icon.storage { background: rgba(168, 85, 247, 0.15); }

.stat-content {
  flex: 1;
  min-width: 0;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: white;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.stat-sub {
  font-size: 10px;
  color: var(--text-muted);
  margin-top: 4px;
}
</style>