<script setup>
import { ref, computed } from 'vue'
import { useEmbeddingStore } from '../../stores/embeddingStore'

const embeddingStore = useEmbeddingStore()

const props = defineProps({
  show: Boolean,
})

const emit = defineEmits(['update:show', 'close'])

const testQuery = ref('What are the key concepts covered in this lecture?')
const selectedModels = ref([])
const isComparing = ref(false)
const comparisonResults = ref(null)

const availableModels = computed(() => embeddingStore.availableModels)

const toggleModelSelection = (modelId) => {
  const index = selectedModels.value.indexOf(modelId)
  if (index > -1) {
    selectedModels.value.splice(index, 1)
  } else {
    if (selectedModels.value.length < 3) {
      selectedModels.value.push(modelId)
    }
  }
}

const isModelSelected = (modelId) => {
  return selectedModels.value.includes(modelId)
}

const runComparison = async () => {
  if (selectedModels.value.length < 2) {
    return
  }

  isComparing.value = true
  comparisonResults.value = null

  try {
    const results = []
    
    for (const modelId of selectedModels.value) {
      const startTime = performance.now()
      const result = await embeddingStore.testModel(modelId, testQuery.value)
      const endTime = performance.now()
      
      results.push({
        modelId,
        modelName: availableModels.value.find(m => m.id === modelId)?.name || modelId,
        results: result?.results || [],
        retrievalTimeMs: result?.retrieval_time_ms || Math.round(endTime - startTime),
        totalResults: result?.total_results || 0,
      })
    }
    
    comparisonResults.value = {
      query: testQuery.value,
      results,
      timestamp: new Date().toISOString(),
    }
  } catch (err) {
    console.error('Comparison failed:', err)
  } finally {
    isComparing.value = false
  }
}

const handleClose = () => {
  emit('update:show', false)
  emit('close')
}

const getSpeedColor = (speed) => {
  switch (speed.toLowerCase()) {
    case 'very fast':
    case 'fast':
      return 'text-green-400'
    case 'medium':
      return 'text-yellow-400'
    case 'slow':
      return 'text-red-400'
    default:
      return 'text-gray-400'
  }
}
</script>

<template>
  <transition name="modal">
    <div v-if="show" class="modal-overlay" @click.self="handleClose">
      <div class="modal-container">
        <div class="modal-header">
          <h3>Compare Embedding Models</h3>
          <button class="modal-close" @click="handleClose" aria-label="Close modal">✕</button>
        </div>
        <div class="modal-body">
          <!-- Model Selection -->
          <div class="section">
            <h4>Select Models (2-3)</h4>
            <div class="model-selection">
              <div
                v-for="model in availableModels"
                :key="model.id"
                class="model-select-card"
                :class="{ selected: isModelSelected(model.id) }"
                @click="toggleModelSelection(model.id)"
              >
                <div class="select-card-header">
                  <span class="model-name">{{ model.name }}</span>
                  <span v-if="model.recommended" class="recommended-badge">Recommended</span>
                </div>
                <div class="select-card-meta">
                  <span>{{ model.dimension }}d</span>
                  <span :class="getSpeedColor(model.speed)">{{ model.speed }}</span>
                </div>
              </div>
            </div>
            <p class="selection-hint">
              Selected: {{ selectedModels.length }} / 3 models
            </p>
          </div>

          <!-- Test Query -->
          <div class="section">
            <h4>Test Query</h4>
            <div class="query-input-group">
              <input
                v-model="testQuery"
                type="text"
                placeholder="Enter a query to compare models..."
                class="query-input"
              />
              <button
                class="btn-compare"
                @click="runComparison"
                :disabled="isComparing || selectedModels.length < 2"
              >
                {{ isComparing ? 'Comparing...' : 'Compare Models' }}
              </button>
            </div>
          </div>

          <!-- Results -->
          <div v-if="comparisonResults" class="section results-section">
            <h4>Comparison Results</h4>
            <div class="results-grid">
              <div
                v-for="(result, index) in comparisonResults.results"
                :key="result.modelId"
                class="result-card"
              >
                <div class="result-header">
                  <h5>{{ result.modelName }}</h5>
                  <span class="result-time">{{ result.retrievalTimeMs }}ms</span>
                </div>
                <div class="result-body">
                  <div v-for="(item, idx) in result.results" :key="idx" class="result-item">
                    <div class="item-rank">#{{ idx + 1 }}</div>
                    <div class="item-content">
                      <div class="item-score">Score: {{ item.score?.toFixed(3) }}</div>
                      <div class="item-text">{{ item.text?.substring(0, 120) }}{{ item.text?.length > 120 ? '...' : '' }}</div>
                    </div>
                  </div>
                  <div v-if="result.results.length === 0" class="no-results">
                    No results found
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Empty State -->
          <div v-if="!comparisonResults && !isComparing" class="empty-state">
            <p>Select 2-3 models and enter a query to compare retrieval performance</p>
          </div>
        </div>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-container {
  width: min(900px, 95vw);
  max-height: 85vh;
  background: rgba(15, 23, 42, 0.95);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  box-shadow: 0 30px 60px rgba(0, 0, 0, 0.8);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  padding: 20px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-main);
}

.modal-close {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.modal-close:hover {
  background: rgba(255, 255, 255, 0.1);
  color: white;
  transform: rotate(90deg);
}

.modal-body {
  padding: 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.section h4 {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.model-selection {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.model-select-card {
  padding: 14px;
  border-radius: 12px;
  border: 1px solid rgba(55, 65, 81, 0.9);
  background: rgba(2, 6, 23, 0.6);
  cursor: pointer;
  transition: all 0.2s;
}

.model-select-card:hover {
  border-color: rgba(255, 255, 255, 0.2);
  background: rgba(2, 6, 23, 0.8);
}

.model-select-card.selected {
  border-color: var(--accent);
  background: rgba(99, 102, 241, 0.15);
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
}

.select-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.model-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
}

.recommended-badge {
  padding: 2px 6px;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--accent), #a855f7);
  color: white;
  font-size: 9px;
  font-weight: 600;
  text-transform: uppercase;
}

.select-card-meta {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: var(--text-muted);
}

.selection-hint {
  margin-top: 8px;
  font-size: 11px;
  color: var(--text-muted);
}

.query-input-group {
  display: flex;
  gap: 12px;
}

.query-input {
  flex: 1;
  padding: 12px 16px;
  border-radius: 12px;
  border: 1px solid rgba(55, 65, 81, 0.9);
  background: rgba(2, 6, 23, 0.8);
  color: var(--text-main);
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}

.query-input:focus {
  border-color: var(--accent);
}

.btn-compare {
  padding: 12px 24px;
  border-radius: 12px;
  border: none;
  background: linear-gradient(135deg, var(--accent), #a855f7);
  color: white;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.btn-compare:hover:not(:disabled) {
  transform: scale(1.02);
  box-shadow: 0 10px 25px rgba(99, 102, 241, 0.4);
}

.btn-compare:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.results-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.result-card {
  border-radius: 12px;
  border: 1px solid rgba(55, 65, 81, 0.5);
  background: rgba(2, 6, 23, 0.6);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.result-header {
  padding: 12px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255, 255, 255, 0.02);
}

.result-header h5 {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
}

.result-time {
  font-size: 12px;
  color: var(--accent);
  font-weight: 600;
}

.result-body {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 300px;
  overflow-y: auto;
}

.result-item {
  display: flex;
  gap: 10px;
  padding: 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.02);
}

.item-rank {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: rgba(99, 102, 241, 0.2);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.item-content {
  flex: 1;
  min-width: 0;
}

.item-score {
  font-size: 10px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.item-text {
  font-size: 11px;
  color: var(--text-main);
  line-height: 1.4;
}

.no-results {
  padding: 20px;
  text-align: center;
  color: var(--text-muted);
  font-size: 12px;
}

.empty-state {
  padding: 60px 20px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
  border: 1px dashed rgba(55, 65, 81, 0.5);
  border-radius: 12px;
  background: rgba(2, 6, 23, 0.3);
}

/* Transitions */
.modal-enter-active,
.modal-leave-active {
  transition: all 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
  transform: scale(0.95) translateY(20px);
}
</style>
