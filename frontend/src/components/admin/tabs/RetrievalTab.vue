<script setup>
import { ref } from 'vue'

const props = defineProps({
  debugResults: Object,
  debugLoading: Boolean
})

const emit = defineEmits(['search'])

const debugQuery = ref('')
const debugParams = ref({
  alpha: 0.3,
  fusion: 'rrf',
  top_k: 5,
  rrf_k: 60
})

const handleSearch = () => {
  if (!debugQuery.value.trim()) return
  emit('search', debugQuery.value, debugParams.value)
}
</script>

<template>
  <div class="tab-content">
    <div class="debug-section">
      <div class="debug-input">
        <input
          v-model="debugQuery"
          type="text"
          placeholder="Enter test query..."
          class="query-input"
          @keyup.enter="handleSearch"
        />
        <button class="search-btn" @click="handleSearch" :disabled="debugLoading">
          {{ debugLoading ? 'Searching...' : 'Search' }}
        </button>
      </div>

      <div class="debug-params">
        <div class="param-group">
          <label>Top K</label>
          <input v-model.number="debugParams.top_k" type="number" min="1" max="20" />
        </div>
        <div class="param-group">
          <label>Alpha (dense weight)</label>
          <input v-model.number="debugParams.alpha" type="number" min="0" max="1" step="0.1" />
        </div>
        <div class="param-group">
          <label>Fusion Method</label>
          <select v-model="debugParams.fusion">
            <option value="rrf">RRF (Reciprocal Rank)</option>
            <option value="weighted">Weighted</option>
          </select>
        </div>
        <div class="param-group">
          <label>RRF K</label>
          <input v-model.number="debugParams.rrf_k" type="number" min="1" max="100" />
        </div>
      </div>

      <div v-if="debugResults" class="debug-results">
        <div class="result-section">
          <h4>BM25 <span class="time">{{ debugResults.bm25?.time_ms }}ms</span></h4>
          <div class="result-list">
            <div v-for="(r, i) in debugResults.bm25?.results" :key="'bm25-'+i" class="result-item">
              <span class="result-rank">{{ i + 1 }}</span>
              <div class="result-content">
                <div class="result-score">Score: {{ r.score }}</div>
                <div class="result-text">{{ r.text }}</div>
                <div class="result-source">{{ r.source }}</div>
              </div>
            </div>
          </div>
        </div>

        <div class="result-section">
          <h4>Dense (Vector) <span class="time">{{ debugResults.dense?.time_ms }}ms</span></h4>
          <div class="result-list">
            <div v-for="(r, i) in debugResults.dense?.results" :key="'dense-'+i" class="result-item">
              <span class="result-rank">{{ i + 1 }}</span>
              <div class="result-content">
                <div class="result-score">Score: {{ r.score }}</div>
                <div class="result-text">{{ r.text }}</div>
                <div class="result-source">{{ r.source }}</div>
              </div>
            </div>
          </div>
        </div>

        <div class="result-section">
          <h4>Hybrid <span class="time">{{ debugResults.hybrid?.time_ms }}ms ({{ debugResults.hybrid?.fusion_method }})</span></h4>
          <div class="result-list">
            <div v-for="(r, i) in debugResults.hybrid?.results" :key="'hybrid-'+i" class="result-item">
              <span class="result-rank">{{ i + 1 }}</span>
              <div class="result-content">
                <div class="result-score">Score: {{ r.score }}</div>
                <div class="result-text">{{ r.text }}</div>
                <div class="result-source">{{ r.source }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tab-content {
  padding: 20px;
}

.debug-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.debug-input {
  display: flex;
  gap: 12px;
}

.query-input {
  flex: 1;
  padding: 12px 16px;
  border-radius: 10px;
  border: 1px solid rgba(55, 65, 81, 0.8);
  background: rgba(2, 6, 23, 0.8);
  color: var(--text-main);
  font-size: 14px;
  outline: none;
}

.query-input:focus {
  border-color: var(--accent);
}

.search-btn {
  padding: 12px 24px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(135deg, var(--accent), #a855f7);
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.search-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 8px 20px -10px rgba(99, 102, 241, 0.5);
}

.search-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.debug-params {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 16px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 12px;
}

.param-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.param-group label {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
}

.param-group input, .param-group select {
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid rgba(55, 65, 81, 0.8);
  background: rgba(2, 6, 23, 0.8);
  color: var(--text-main);
  font-size: 13px;
  outline: none;
}

.param-group input:focus, .param-group select:focus {
  border-color: var(--accent);
}

.debug-results {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.result-section {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  padding: 16px;
}

.result-section h4 {
  font-size: 13px;
  font-weight: 600;
  color: white;
  margin-bottom: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.time {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: normal;
}

.result-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 400px;
  overflow-y: auto;
}

.result-item {
  display: flex;
  gap: 10px;
  padding: 10px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
}

.result-rank {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(99, 102, 241, 0.2);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.result-content {
  flex: 1;
  min-width: 0;
}

.result-score {
  font-size: 11px;
  color: var(--accent);
  font-weight: 600;
  margin-bottom: 4px;
}

.result-text {
  font-size: 12px;
  color: var(--text-main);
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.result-source {
  font-size: 10px;
  color: var(--text-muted);
  margin-top: 4px;
}

@media (max-width: 900px) {
  .debug-results {
    grid-template-columns: 1fr;
  }
}
</style>