<script setup>
import { ref } from 'vue'

const props = defineProps({
  config: Object,
  savingConfig: Boolean,
  reindexing: Boolean
})

const emit = defineEmits(['save-config', 'reindex'])
</script>

<template>
  <div class="config-panel">
    <div class="config-header">
      <span class="config-title">⚙️ RAG Configuration</span>
    </div>
    <div class="config-grid">
      <div class="config-item">
        <label>Chunk Size</label>
        <input v-model.number="config.chunk_size" type="number" min="100" max="2000" step="50" />
      </div>
      <div class="config-item">
        <label>Chunk Overlap</label>
        <input v-model.number="config.chunk_overlap" type="number" min="0" max="500" step="10" />
      </div>
      <div class="config-item">
        <label>Top K</label>
        <input v-model.number="config.top_k" type="number" min="1" max="20" step="1" />
      </div>
      <div class="config-item">
        <label>Temperature</label>
        <input v-model.number="config.temperature" type="number" min="0" max="2" step="0.1" />
      </div>
    </div>
    <div class="config-actions">
      <button class="btn btn-primary" @click="emit('save-config')" :disabled="savingConfig">
        {{ savingConfig ? 'Saving...' : 'Save Configuration' }}
      </button>
      <button class="btn btn-danger" @click="emit('reindex')" :disabled="reindexing">
        {{ reindexing ? 'Reindexing...' : '🔄 Rebuild Index' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.config-panel {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  padding: 16px;
}

.config-header {
  margin-bottom: 16px;
}

.config-title {
  font-size: 14px;
  font-weight: 600;
  color: white;
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.config-item label {
  display: block;
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 6px;
  text-transform: uppercase;
}

.config-item input {
  width: 100%;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid rgba(55, 65, 81, 0.8);
  background: rgba(2, 6, 23, 0.8);
  color: var(--text-main);
  font-size: 13px;
  outline: none;
}

.config-item input:focus {
  border-color: var(--accent);
}

.config-actions {
  display: flex;
  gap: 12px;
}

.btn {
  padding: 10px 20px;
  border-radius: 8px;
  border: none;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary {
  background: linear-gradient(135deg, var(--accent), #a855f7);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 8px 20px -10px rgba(99, 102, 241, 0.5);
}

.btn-danger {
  background: rgba(239, 68, 68, 0.2);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #fca5a5;
}

.btn-danger:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.3);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 900px) {
  .config-grid {
    grid-template-columns: 1fr 1fr;
  }
}
</style>