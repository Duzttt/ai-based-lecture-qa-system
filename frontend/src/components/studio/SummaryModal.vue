<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  show: Boolean,
  selectedDocs: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['update:show', 'close', 'generate'])

// Summary configuration
const config = ref({
  length: 'medium',
  style: 'narrative',
  language: 'zh',
  include_citations: true,
  include_comparison: true,
})

const isGenerating = ref(false)
const error = ref('')

const selectedCount = computed(() => props.selectedDocs.length)

const lengthOptions = [
  { value: 'short', label: 'Short', desc: '3-5 sentences, about 150 words' },
  { value: 'medium', label: 'Medium', desc: '8-12 sentences, about 300 words' },
  { value: 'detailed', label: 'Detailed', desc: '15-20 sentences, about 600 words' },
]

const styleOptions = [
  { value: 'bullets', label: 'Bulleted', desc: 'List core content in bullet points' },
  { value: 'narrative', label: 'Narrative', desc: 'Summarize in a coherent narrative style' },
  { value: 'academic', label: 'Academic', desc: 'Use academic language with key arguments' },
  { value: 'executive', label: 'Executive', desc: 'Highlight key findings and recommendations' },
]

const languageOptions = [
  { value: 'zh', label: 'Chinese' },
  { value: 'en', label: 'English' },
]

const handleClose = () => {
  emit('update:show', false)
  emit('close')
  error.value = ''
}

const handleGenerate = async () => {
  if (props.selectedDocs.length === 0) {
    error.value = 'Please select at least one document'
    return
  }

  isGenerating.value = true
  error.value = ''

  try {
    emit('generate', { ...config.value })
  } catch (err) {
    error.value = err.message
  } finally {
    isGenerating.value = false
  }
}

const resetConfig = () => {
  config.value = {
    length: 'medium',
    style: 'narrative',
    language: 'zh',
    include_citations: true,
    include_comparison: props.selectedDocs.length > 1,
  }
}
</script>

<template>
  <transition name="modal">
    <div v-if="show" class="modal-overlay" @click.self="handleClose">
      <div class="modal-container">
        <div class="modal-header">
          <h3>📝 Document Summary</h3>
          <button class="modal-close" @click="handleClose" aria-label="Close summary modal">✕</button>
        </div>
        <div class="modal-body">
          <!-- Selected Documents Info -->
          <div class="selected-docs-info">
            <div class="info-header">
              <span class="info-icon">📄</span>
              <span class="info-text">{{ selectedCount }} document(s) selected</span>
            </div>
            <div class="doc-list">
              <div v-for="doc in selectedDocs" :key="doc" class="doc-item">
                <span class="doc-icon">📋</span>
                <span class="doc-name" :title="doc">{{ doc }}</span>
              </div>
            </div>
          </div>

          <!-- Configuration Options -->
          <div class="config-section">
            <h4>Summary Configuration</h4>
            
            <!-- Length -->
            <div class="config-item">
              <label class="config-label">Summary Length</label>
              <div class="option-grid">
                <button
                  v-for="opt in lengthOptions"
                  :key="opt.value"
                  class="option-card"
                  :class="{ active: config.length === opt.value }"
                  @click="config.length = opt.value"
                >
                  <span class="option-title">{{ opt.label }}</span>
                  <span class="option-desc">{{ opt.desc }}</span>
                </button>
              </div>
            </div>

            <!-- Style -->
            <div class="config-item">
              <label class="config-label">Summary Style</label>
              <div class="option-grid">
                <button
                  v-for="opt in styleOptions"
                  :key="opt.value"
                  class="option-card"
                  :class="{ active: config.style === opt.value }"
                  @click="config.style = opt.value"
                >
                  <span class="option-title">{{ opt.label }}</span>
                  <span class="option-desc">{{ opt.desc }}</span>
                </button>
              </div>
            </div>

            <!-- Language -->
            <div class="config-item">
              <label class="config-label">Output Language</label>
              <div class="option-row">
                <button
                  v-for="opt in languageOptions"
                  :key="opt.value"
                  class="option-btn"
                  :class="{ active: config.language === opt.value }"
                  @click="config.language = opt.value"
                >
                  {{ opt.label }}
                </button>
              </div>
            </div>

            <!-- Checkboxes -->
            <div class="config-item checkboxes">
              <label class="checkbox-label">
                <input
                  type="checkbox"
                  v-model="config.include_citations"
                />
                <span>Include key citations</span>
              </label>
              <label v-if="selectedCount > 1" class="checkbox-label">
                <input
                  type="checkbox"
                  v-model="config.include_comparison"
                />
                <span>Generate comparison table</span>
              </label>
            </div>
          </div>

          <!-- Error Message -->
          <div v-if="error" class="error-message">
            {{ error }}
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-reset" @click="resetConfig" :disabled="isGenerating">
            🔄 Reset
          </button>
          <div class="modal-actions">
            <button class="btn-cancel" @click="handleClose" :disabled="isGenerating">
              Cancel
            </button>
            <button 
              class="btn-generate" 
              @click="handleGenerate"
              :disabled="isGenerating || selectedCount === 0"
            >
              {{ isGenerating ? 'Generating...' : '✨ Generate Summary' }}
            </button>
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
  width: min(600px, 90vw);
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
  gap: 20px;
}

/* Selected Docs Info */
.selected-docs-info {
  background: rgba(2, 6, 23, 0.6);
  border: 1px solid rgba(55, 65, 81, 0.8);
  border-radius: 12px;
  padding: 12px;
}

.info-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.info-icon {
  font-size: 16px;
}

.info-text {
  font-size: 13px;
  font-weight: 600;
  color: var(--accent);
}

.doc-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 120px;
  overflow-y: auto;
}

.doc-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
  font-size: 11px;
  color: var(--text-muted);
}

.doc-icon {
  font-size: 14px;
}

.doc-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Config Section */
.config-section h4 {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.config-item {
  margin-bottom: 16px;
}

.config-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-main);
  margin-bottom: 8px;
}

.option-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.option-card {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(55, 65, 81, 0.9);
  background: rgba(2, 6, 23, 0.6);
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: left;
}

.option-card:hover {
  border-color: rgba(99, 102, 241, 0.5);
  background: rgba(2, 6, 23, 0.8);
}

.option-card.active {
  border-color: var(--accent);
  background: rgba(99, 102, 241, 0.15);
  box-shadow: 0 0 0 1px rgba(99, 102, 241, 0.2);
}

.option-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-main);
}

.option-desc {
  font-size: 10px;
  color: var(--text-muted);
}

.option-row {
  display: flex;
  gap: 8px;
}

.option-btn {
  flex: 1;
  padding: 8px 16px;
  border-radius: 8px;
  border: 1px solid rgba(55, 65, 81, 0.9);
  background: rgba(2, 6, 23, 0.6);
  color: var(--text-main);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.option-btn:hover {
  border-color: rgba(99, 102, 241, 0.5);
}

.option-btn.active {
  border-color: var(--accent);
  background: rgba(99, 102, 241, 0.15);
  color: var(--accent);
}

.checkboxes {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-main);
  cursor: pointer;
}

.checkbox-label input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: var(--accent);
  cursor: pointer;
}

.error-message {
  padding: 10px 14px;
  border-radius: 10px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #fca5a5;
  font-size: 12px;
}

/* Modal Footer */
.modal-footer {
  padding: 16px 24px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(0, 0, 0, 0.2);
}

.btn-reset {
  padding: 8px 16px;
  border-radius: 8px;
  border: 1px solid rgba(55, 65, 81, 0.9);
  background: rgba(2, 6, 23, 0.6);
  color: var(--text-muted);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-reset:hover:not(:disabled) {
  border-color: var(--text-main);
  color: var(--text-main);
}

.btn-reset:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.modal-actions {
  display: flex;
  gap: 10px;
}

.btn-cancel {
  padding: 10px 20px;
  border-radius: 10px;
  border: 1px solid rgba(55, 65, 81, 0.9);
  background: rgba(2, 6, 23, 0.6);
  color: var(--text-main);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-cancel:hover:not(:disabled) {
  border-color: var(--text-muted);
}

.btn-cancel:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-generate {
  padding: 10px 24px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(135deg, var(--accent), #a855f7);
  color: white;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-generate:hover:not(:disabled) {
  transform: scale(1.02);
  box-shadow: 0 10px 25px rgba(99, 102, 241, 0.4);
}

.btn-generate:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
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
