<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useLlmSettingsStore } from '../../stores/llmSettingsStore'

const store = useLlmSettingsStore()
const isOpen = ref(false)
const switchMessage = ref('')
const switchStatus = ref('')

const PROVIDER_ICONS = {
  gemini: '✨',
  openrouter: '🔗',
  local_qwen: '🏠',
}

const toggle = () => {
  isOpen.value = !isOpen.value
}

const handleSelect = async (providerId, model) => {
  if (providerId === store.currentProvider && model === store.currentModel) {
    isOpen.value = false
    return
  }

  const success = await store.switchProvider(providerId, model)
  if (success) {
    switchStatus.value = 'success'
    switchMessage.value = `Switched to ${providerId}`
  } else {
    switchStatus.value = 'error'
    switchMessage.value = store.error || 'Failed to switch'
  }

  isOpen.value = false
  setTimeout(() => {
    switchMessage.value = ''
    switchStatus.value = ''
  }, 3000)
}

const handleClickOutside = (e) => {
  if (!e.target.closest('.provider-switcher')) {
    isOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<template>
  <div class="provider-switcher">
    <button class="switcher-trigger pill-btn" @click="toggle">
      <span class="switcher-icon">{{ PROVIDER_ICONS[store.currentProvider] || '🤖' }}</span>
      <span class="switcher-label">{{ store.currentProviderName || 'LLM' }}</span>
      <span class="switcher-chevron" :class="{ open: isOpen }">▾</span>
    </button>

    <div v-if="switchMessage" class="switcher-toast" :class="switchStatus">
      {{ switchMessage }}
    </div>

    <div v-if="isOpen" class="switcher-dropdown">
      <div v-if="store.isSwitching" class="switcher-loading">
        Switching...
      </div>
      <template v-else>
        <div
          v-for="provider in store.providers"
          :key="provider.id"
          class="provider-group"
        >
          <div class="provider-group-header">
            <span>{{ PROVIDER_ICONS[provider.id] || '🤖' }}</span>
            <span>{{ provider.name }}</span>
            <span v-if="!provider.has_api_key && provider.requires_api_key" class="no-key-badge">
              No API Key
            </span>
          </div>
          <button
            v-for="model in provider.models"
            :key="model"
            class="model-option"
            :class="{
              active: store.currentProvider === provider.id && store.currentModel === model,
            }"
            @click="handleSelect(provider.id, model)"
          >
            <span class="model-name">{{ model }}</span>
            <span v-if="store.currentProvider === provider.id && store.currentModel === model" class="active-dot">●</span>
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.provider-switcher {
  position: relative;
}

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

.switcher-chevron {
  font-size: 10px;
  transition: transform 0.2s;
  color: var(--text-muted);
}

.switcher-chevron.open {
  transform: rotate(180deg);
}

.switcher-toast {
  position: absolute;
  top: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 12px;
  white-space: nowrap;
  z-index: 100;
  animation: fadeIn 0.2s ease;
}

.switcher-toast.success {
  background: rgba(34, 197, 94, 0.15);
  border: 1px solid rgba(34, 197, 94, 0.5);
  color: #86efac;
}

.switcher-toast.error {
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.5);
  color: #fecaca;
}

.switcher-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
  min-width: 220px;
  background: rgba(15, 23, 42, 0.95);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 14px;
  box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.8);
  z-index: 999;
  overflow: hidden;
  animation: slideDown 0.2s ease;
}

.switcher-loading {
  padding: 16px;
  text-align: center;
  font-size: 12px;
  color: var(--text-muted);
}

.provider-group {
  padding: 6px 0;
}

.provider-group + .provider-group {
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.provider-group-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.no-key-badge {
  margin-left: auto;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 999px;
  background: rgba(239, 68, 68, 0.15);
  color: #fca5a5;
  text-transform: none;
  letter-spacing: 0;
}

.model-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 7px 14px 7px 30px;
  border: none;
  background: none;
  color: var(--text-main);
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s;
  text-align: left;
}

.model-option:hover {
  background: rgba(255, 255, 255, 0.06);
}

.model-option.active {
  background: rgba(99, 102, 241, 0.12);
  color: #a5b4fc;
}

.model-name {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 11px;
}

.active-dot {
  color: #a855f7;
  font-size: 8px;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(-6px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}
</style>
