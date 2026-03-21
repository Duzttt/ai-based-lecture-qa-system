<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  show: Boolean,
})

const emit = defineEmits(['update:show'])

const llmProvider = ref('gemini')
const apiKey = ref('')
const model = ref('')
const temperature = ref(0.7)
const topK = ref(3)
const error = ref('')

const handleClose = () => {
  emit('update:show', false)
}

const handleSave = async () => {
  try {
    const response = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider: llmProvider.value,
        model: model.value,
        api_key: apiKey.value,
      }),
    })
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || errorData.error || 'Failed to save settings')
    }
    
    handleClose()
  } catch (err) {
    error.value = err.message
  }
}

watch(() => props.show, async (newVal) => {
  if (newVal) {
    error.value = ''
    try {
      const response = await fetch('/api/settings')
      if (response.ok) {
        const data = await response.json()
        llmProvider.value = data.provider || 'gemini'
        model.value = data.model || ''
        apiKey.value = ''
      }
    } catch (err) {
      console.error('Failed to load settings:', err)
    }
  }
})
</script>

<template>
  <div v-if="show" class="modal-overlay" @click.self="handleClose">
    <div class="modal-container">
      <div class="modal-header">
        <h3>Settings</h3>
        <button class="modal-close" @click="handleClose">✕</button>
      </div>
      <div class="modal-body">
        <div class="modal-section">
          <h4>LLM Provider</h4>
          <div class="form-row">
            <label>Provider</label>
            <select v-model="llmProvider">
              <option value="gemini">Google Gemini</option>
              <option value="openrouter">OpenRouter</option>
              <option value="local_qwen">Local Qwen (Ollama)</option>
            </select>
          </div>
          <div class="form-row">
            <label>API Key</label>
            <input 
              v-model="apiKey" 
              type="password" 
              placeholder="Enter your API key"
            />
          </div>
          <div class="form-row">
            <label>Model</label>
            <input 
              v-model="model" 
              type="text" 
              placeholder="e.g., gemini-2.5-flash"
            />
          </div>
        </div>
        <div class="modal-section">
          <h4>RAG Settings</h4>
          <div class="form-row">
            <label>Temperature: {{ temperature }}</label>
            <input 
              v-model="temperature" 
              type="range" 
              min="0" 
              max="1" 
              step="0.1"
            />
          </div>
          <div class="form-row">
            <label>Top K: {{ topK }}</label>
            <input 
              v-model="topK" 
              type="range" 
              min="1" 
              max="10" 
              step="1"
            />
          </div>
        </div>
        <div v-if="error" class="settings-error">{{ error }}</div>
      </div>
      <div class="modal-footer">
        <span class="selected-count">Configure your LLM preferences</span>
        <div class="modal-actions">
          <button class="modal-btn secondary" @click="handleClose">Cancel</button>
          <button class="modal-btn primary" @click="handleSave">Save</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: fadeIn 0.2s ease;
}

.modal-container {
  width: min(520px, 90vw);
  background: rgba(15, 23, 42, 0.8);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 24px;
  box-shadow:
    0 30px 60px -20px rgba(0, 0, 0, 0.8),
    inset 0 1px 1px rgba(255, 255, 255, 0.1);
  animation: slideUp 0.3s ease;
  overflow: hidden;
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
  background: linear-gradient(135deg, #fff, #cbd5e1);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.modal-close {
  width: 32px;
  height: 32px;
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
  padding: 16px 24px 12px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-height: 60vh;
  overflow-y: auto;
}

.modal-section h4 {
  margin: 0 0 8px;
  font-size: 13px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 8px;
}

.form-row label {
  font-size: 12px;
  color: var(--text-muted);
}

.form-row input,
.form-row select {
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid rgba(55, 65, 81, 0.9);
  background: #020617;
  color: var(--text-main);
  font-size: 12px;
  outline: none;
}

.form-row input:focus,
.form-row select:focus {
  border-color: var(--accent);
}

.form-row input[type="range"] {
  padding: 0;
  height: 6px;
  border-radius: 3px;
  -webkit-appearance: none;
}

.settings-error {
  margin-top: 6px;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.7);
  color: #fecaca;
  font-size: 12px;
}

.modal-footer {
  padding: 16px 24px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(0, 0, 0, 0.2);
}

.selected-count {
  font-size: 13px;
  color: var(--text-muted);
}

.modal-actions {
  display: flex;
  gap: 12px;
}

.modal-btn {
  padding: 8px 20px;
  border-radius: 30px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  color: white;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.modal-btn.secondary:hover {
  background: rgba(255, 255, 255, 0.1);
}

.modal-btn.primary {
  background: linear-gradient(135deg, var(--accent), #a855f7);
  border: none;
  box-shadow: 0 10px 20px -10px var(--accent);
}

.modal-btn.primary:hover {
  transform: scale(1.05);
  filter: brightness(1.1);
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
