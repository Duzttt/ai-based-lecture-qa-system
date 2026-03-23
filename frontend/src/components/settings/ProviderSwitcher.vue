<script setup>
import { ref } from 'vue'
import { useLlmSettingsStore } from '../../stores/llmSettingsStore'

const store = useLlmSettingsStore()
const showModal = ref(false)

const PROVIDER_ICONS = {
  gemini: '✨',
  openrouter: '🔗',
  local_qwen: '🏠',
}

const openModal = () => {
  showModal.value = true
}

const closeModal = () => {
  showModal.value = false
}

const handleSelect = async (providerId, model) => {
  if (providerId === store.currentProvider && model === store.currentModel) {
    closeModal()
    return
  }

  const success = await store.switchProvider(providerId, model)
  if (success) {
    closeModal()
  }
}
</script>

<template>
  <button class="switcher-trigger pill-btn" @click="openModal">
    <span class="switcher-icon">{{ PROVIDER_ICONS[store.currentProvider] || '🤖' }}</span>
    <span class="switcher-label">{{ store.currentProviderName || 'LLM' }}</span>
  </button>

  <Teleport to="body">
    <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal-container">
        <div class="modal-header">
          <h3>Switch LLM Provider</h3>
          <button class="modal-close" @click="closeModal">✕</button>
        </div>

        <div class="modal-body">
          <div v-if="store.isSwitching" class="switching-state">
            <div class="spinner"></div>
            <span>Switching provider...</span>
          </div>

          <template v-else>
            <div
              v-for="provider in store.providers"
              :key="provider.id"
              class="provider-section"
            >
              <div class="provider-title">
                <span class="provider-title-icon">{{ PROVIDER_ICONS[provider.id] || '🤖' }}</span>
                <span class="provider-title-name">{{ provider.name }}</span>
                <span
                  v-if="provider.has_api_key"
                  class="status-badge ready"
                >
                  Ready
                </span>
                <span
                  v-else-if="provider.requires_api_key"
                  class="status-badge no-key"
                >
                  No API Key
                </span>
                <span v-else class="status-badge local">
                  Local
                </span>
              </div>

              <div class="model-grid">
                <button
                  v-for="model in provider.models"
                  :key="model"
                  class="model-card"
                  :class="{
                    active: store.currentProvider === provider.id && store.currentModel === model,
                  }"
                  @click="handleSelect(provider.id, model)"
                >
                  <div class="model-card-name">{{ model }}</div>
                  <div
                    v-if="store.currentProvider === provider.id && store.currentModel === model"
                    class="model-card-active"
                  >
                    Active
                  </div>
                </button>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.switcher-trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}

.switcher-icon {
  font-size: 13px;
}

.switcher-label {
  font-size: 12px;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

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
  max-height: 80vh;
  background: rgba(15, 23, 42, 0.95);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 24px;
  box-shadow:
    0 30px 60px -20px rgba(0, 0, 0, 0.8),
    inset 0 1px 1px rgba(255, 255, 255, 0.1);
  animation: slideUp 0.3s ease;
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
  padding: 20px 24px 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.switching-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px 0;
  color: var(--text-muted);
  font-size: 14px;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(168, 85, 247, 0.3);
  border-top-color: #a855f7;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.provider-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.provider-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.provider-title-icon {
  font-size: 16px;
}

.provider-title-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
}

.status-badge {
  margin-left: auto;
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 999px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.status-badge.ready {
  background: rgba(34, 197, 94, 0.15);
  color: #86efac;
}

.status-badge.no-key {
  background: rgba(239, 68, 68, 0.15);
  color: #fca5a5;
}

.status-badge.local {
  background: rgba(99, 102, 241, 0.15);
  color: #a5b4fc;
}

.model-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.model-card {
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
  cursor: pointer;
  text-align: left;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.model-card:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.15);
  transform: translateY(-1px);
}

.model-card.active {
  background: rgba(99, 102, 241, 0.12);
  border-color: rgba(129, 140, 248, 0.5);
}

.model-card-name {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 12px;
  color: var(--text-main);
  word-break: break-all;
}

.model-card.active .model-card-name {
  color: #a5b4fc;
}

.model-card-active {
  font-size: 10px;
  color: #a855f7;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
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

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
