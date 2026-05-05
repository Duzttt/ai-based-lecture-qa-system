<script setup>
import { ref, computed, onMounted } from 'vue'
import { useEmbeddingStore } from '../../stores/embeddingStore'

const props = defineProps({
  compact: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['model-changed'])

const embeddingStore = useEmbeddingStore()
const showDropdown = ref(false)
const showTestModal = ref(false)
const testQuery = ref('')
const selectedModelForTest = ref(null)

const isDropdownOpen = computed(() => showDropdown.value)
const currentModel = computed(() => embeddingStore.currentModelInfo)
const isChanging = computed(() => embeddingStore.isModelChanging)

onMounted(async () => {
  await embeddingStore.loadCurrentModel()
  await embeddingStore.loadAvailableModels()
})

const toggleDropdown = () => {
  showDropdown.value = !showDropdown.value
}

const closeDropdown = () => {
  showDropdown.value = false
}

const selectModel = async (model) => {
  if (model.id === currentModel.value?.id) {
    closeDropdown()
    return
  }

  const success = await embeddingStore.switchModel(model.id, { reindex: false })
  if (success) {
    emit('model-changed', model)
  }
  closeDropdown()
}

const openTestModal = (model) => {
  selectedModelForTest.value = model
  testQuery.value = ''
  showTestModal.value = true
}

const closeTestModal = () => {
  showTestModal.value = false
  selectedModelForTest.value = null
  testQuery.value = ''
}

const runTest = async () => {
  if (!selectedModelForTest.value) return
  
  await embeddingStore.testModel(
    selectedModelForTest.value.id,
    testQuery.value || 'What is the main topic?'
  )
}

const getSpeedColor = (speed) => {
  if (!speed) {
    return 'text-gray-400'
  }

  const normalized = String(speed).toLowerCase()

  switch (normalized) {
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
  <div class="embedding-model-selector" :class="{ compact }">
    <div class="selector-header">
      <div class="selector-title">
        <span class="title-text">Embedding Model</span>
        <span class="title-sub">Choose retrieval model</span>
      </div>
      <div class="selector-actions">
        <button
          v-if="currentModel"
          class="btn-test"
          @click="openTestModal(currentModel)"
          :disabled="isChanging"
        >
          Test
        </button>
      </div>
    </div>

    <div class="selector-body">
      <!-- Current Model Display -->
      <div class="current-model" @click="toggleDropdown" :class="{ loading: isChanging }">
        <div class="model-info">
          <div class="model-name">
            {{ currentModel?.name || 'Loading...' }}
            <span v-if="currentModel?.recommended" class="recommended-badge">Recommended</span>
          </div>
          <div class="model-meta">
            <span class="meta-item">
              <span class="meta-label">Dimension:</span>
              <span class="meta-value">{{ currentModel?.dimension || '-' }}</span>
            </span>
            <span class="meta-item">
              <span class="meta-label">Speed:</span>
              <span class="meta-value" :class="getSpeedColor(currentModel?.speed)">
                {{ currentModel?.speed || '-' }}
              </span>
            </span>
            <span class="meta-item">
              <span class="meta-label">Memory:</span>
              <span class="meta-value">{{ currentModel?.memory || '-' }}</span>
            </span>
          </div>
        </div>
        <div class="model-status">
          <span v-if="isChanging" class="loading-spinner"></span>
          <span v-else class="status-indicator active"></span>
          <svg class="chevron" :class="{ open: isDropdownOpen }" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M6 9l6 6 6-6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
      </div>

      <!-- Dropdown Menu -->
      <transition name="dropdown">
        <div v-if="isDropdownOpen" class="dropdown-menu" v-click-outside="closeDropdown">
          <div class="dropdown-header">
            <span>Available Models</span>
          </div>
          <div class="dropdown-content">
            <div
              v-for="model in embeddingStore.availableModels"
              :key="model.id"
              class="model-option"
              :class="{ 
                active: currentModel?.id === model.id,
                disabled: isChanging 
              }"
              @click="selectModel(model)"
            >
              <div class="option-main">
                <div class="option-name">
                  {{ model.name }}
                  <span v-if="model.recommended" class="recommended-badge mini">Recommended</span>
                </div>
                <div class="option-id">{{ model.id }}</div>
              </div>
              <div class="option-meta">
                <span class="option-dim">{{ model.dimension }}d</span>
                <span class="option-speed" :class="getSpeedColor(model.speed)">{{ model.speed }}</span>
              </div>
              <div class="option-actions">
                <button class="btn-info" @click.stop="openTestModal(model)" title="Test model">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="16" height="16">
                    <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" stroke-width="2" stroke-linecap="round"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </transition>

      <!-- Error Display -->
      <div v-if="embeddingStore.error" class="error-message">
        {{ embeddingStore.error }}
      </div>
    </div>

    <!-- Test Modal -->
    <transition name="modal">
      <div v-if="showTestModal" class="modal-overlay" @click.self="closeTestModal">
        <div class="modal-container">
          <div class="modal-header">
            <h3>Test Model: {{ selectedModelForTest?.name }}</h3>
            <button class="modal-close" @click="closeTestModal">✕</button>
          </div>
          <div class="modal-body">
            <div class="test-input-group">
              <label>Test Query</label>
              <input
                v-model="testQuery"
                type="text"
                placeholder="Enter a test query..."
                @keyup.enter="runTest"
              />
              <button class="btn-run-test" @click="runTest" :disabled="embeddingStore.isTesting">
                {{ embeddingStore.isTesting ? 'Testing...' : 'Run Test' }}
              </button>
            </div>

            <div v-if="embeddingStore.lastTestResults && embeddingStore.lastTestResults.modelId === selectedModelForTest?.id" class="test-results">
              <div class="results-header">
                <h4>Results</h4>
                <span class="results-time">{{ embeddingStore.lastTestResults.retrievalTimeMs }}ms</span>
              </div>
              <div class="results-list">
                <div v-for="(result, index) in embeddingStore.lastTestResults.results" :key="index" class="result-item">
                  <div class="result-score">
                    <span class="score-label">Score</span>
                    <span class="score-value">{{ result.score?.toFixed(3) || result.distance?.toFixed(3) }}</span>
                  </div>
                  <div class="result-text">{{ result.text?.substring(0, 150) }}{{ result.text?.length > 150 ? '...' : '' }}</div>
                  <div class="result-meta">
                    <span>{{ result.source }}</span>
                    <span v-if="result.page">Page {{ result.page }}</span>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="!embeddingStore.lastTestResults" class="test-placeholder">
              <p>Enter a query and click "Run Test" to see retrieval results</p>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.embedding-model-selector {
  background: linear-gradient(
    135deg,
    rgba(15, 25, 45, 0.4) 0%,
    rgba(25, 35, 60, 0.5) 100%
  );
  border-radius: var(--radius-lg);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-top-color: rgba(255, 255, 255, 0.12);
  border-left-color: rgba(255, 255, 255, 0.12);
  overflow: hidden;
  backdrop-filter: blur(15px) saturate(180%);
  -webkit-backdrop-filter: blur(15px) saturate(180%);
  box-shadow:
    0 15px 30px -15px rgba(0, 0, 0, 0.6),
    inset 0 1px 1px rgba(255, 255, 255, 0.1),
    inset 0 -2px 2px rgba(0, 0, 0, 0.2);
}

.selector-header {
  padding: 10px 12px;
  border-bottom: 1px solid rgba(31, 41, 55, 0.9);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.selector-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.title-text {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-main);
}

.title-sub {
  font-size: 10px;
  color: var(--text-muted);
}

.btn-test {
  padding: 4px 10px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-main);
  font-size: 10px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-test:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.1);
  border-color: var(--accent);
}

.btn-test:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.selector-body {
  padding: 12px;
  position: relative;
}

.current-model {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(55, 65, 81, 0.9);
  background: rgba(2, 6, 23, 0.8);
  cursor: pointer;
  transition: all 0.2s;
}

.current-model:hover:not(.loading) {
  border-color: rgba(255, 255, 255, 0.2);
  background: rgba(2, 6, 23, 1);
}

.current-model.loading {
  opacity: 0.7;
  cursor: wait;
}

.model-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
  min-width: 0;
}

.model-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
  display: flex;
  align-items: center;
  gap: 6px;
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

.recommended-badge.mini {
  padding: 1px 4px;
  font-size: 8px;
}

.model-meta {
  display: flex;
  gap: 12px;
  font-size: 10px;
  color: var(--text-muted);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.meta-label {
  opacity: 0.7;
}

.meta-value {
  color: var(--text-main);
  font-weight: 500;
}

.model-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.loading-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.1);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.3);
}

.status-indicator.active {
  background: #10b981;
  box-shadow: 0 0 8px rgba(16, 185, 129, 0.5);
}

.chevron {
  width: 16px;
  height: 16px;
  color: var(--text-muted);
  transition: transform 0.2s;
}

.chevron.open {
  transform: rotate(180deg);
}

/* Dropdown */
.dropdown-menu {
  position: absolute;
  top: calc(100% + 8px);
  left: 12px;
  right: 12px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(2, 6, 23, 0.98);
  backdrop-filter: blur(20px);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6);
  z-index: 100;
  overflow: hidden;
}

.dropdown-header {
  padding: 8px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.dropdown-content {
  max-height: 280px;
  overflow-y: auto;
}

.model-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  cursor: pointer;
  transition: all 0.2s;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
}

.model-option:last-child {
  border-bottom: none;
}

.model-option:hover:not(.disabled) {
  background: rgba(255, 255, 255, 0.05);
}

.model-option.active {
  background: rgba(99, 102, 241, 0.15);
  border-left: 3px solid var(--accent);
}

.model-option.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.option-main {
  flex: 1;
  min-width: 0;
}

.option-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-main);
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 2px;
}

.option-id {
  font-size: 9px;
  color: var(--text-muted);
  font-family: 'Monaco', 'Consolas', monospace;
}

.option-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  font-size: 10px;
}

.option-dim {
  color: var(--text-muted);
}

.option-speed {
  font-weight: 500;
}

.option-actions {
  display: flex;
  gap: 4px;
}

.btn-info {
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
  transition: all 0.2s;
}

.btn-info:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--accent);
  border-color: var(--accent);
}

.error-message {
  margin-top: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.5);
  color: #fecaca;
  font-size: 11px;
}

/* Modal */
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
  width: min(600px, 90vw);
  max-height: 80vh;
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
  font-size: 16px;
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
  padding: 20px 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.test-input-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.test-input-group label {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 500;
}

.test-input-group input {
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid rgba(55, 65, 81, 0.9);
  background: rgba(2, 6, 23, 0.8);
  color: var(--text-main);
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}

.test-input-group input:focus {
  border-color: var(--accent);
}

.btn-run-test {
  padding: 10px 20px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(135deg, var(--accent), #a855f7);
  color: white;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-run-test:hover:not(:disabled) {
  transform: scale(1.02);
  box-shadow: 0 10px 25px rgba(99, 102, 241, 0.4);
}

.btn-run-test:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.test-results {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.results-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.results-header h4 {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.results-time {
  font-size: 12px;
  color: var(--accent);
  font-weight: 600;
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.result-item {
  padding: 12px;
  border-radius: 10px;
  border: 1px solid rgba(55, 65, 81, 0.5);
  background: rgba(2, 6, 23, 0.6);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.result-score {
  display: flex;
  align-items: center;
  gap: 6px;
}

.score-label {
  font-size: 10px;
  color: var(--text-muted);
  text-transform: uppercase;
}

.score-value {
  font-size: 12px;
  font-weight: 600;
  color: var(--accent);
}

.result-text {
  font-size: 12px;
  color: var(--text-main);
  line-height: 1.5;
}

.result-meta {
  display: flex;
  gap: 12px;
  font-size: 10px;
  color: var(--text-muted);
}

.test-placeholder {
  padding: 40px 20px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
}

/* Transitions */
.dropdown-enter-active,
.dropdown-leave-active {
  transition: all 0.2s ease;
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

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
