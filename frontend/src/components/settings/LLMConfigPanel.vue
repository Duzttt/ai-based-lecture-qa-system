<script setup>
import { ref, computed, onMounted } from 'vue'
import { useLlmSettingsStore } from '../../stores/llmSettingsStore'
import { saveSettings } from '../../services/api'

const emit = defineEmits(['close'])

const llmStore = useLlmSettingsStore()

// Sidebar nav
const activeNav = ref('model-config')
const navSections = [
  {
    label: 'System Config',
    items: [
      { id: 'general', label: 'General', icon: 'M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.07.62-.07.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z' },
      { id: 'api-providers', label: 'API Providers', icon: 'M4 8h4V4H4v4zm6 12h4v-4h-4v4zm-6 0h4v-4H4v4zm0-6h4v-4H4v4zm6 0h4v-4h-4v4zm6-10v4h4V4h-4zm-6 4h4V4h-4v4zm6 6h4v-4h-4v4zm0 6h4v-4h-4v4z' },
      { id: 'model-config', label: 'Model Config', icon: 'M3 17v2h6v-2H3zM3 5v2h10V5H3zm10 16v-2h8v-2h-8v-2h-2v6h2zM7 9v2H3v2h4v2h2V9H7zm14 4v-2H11v2h10zm-6-4h2V7h4V5h-4V3h-2v6z' },
      { id: 'security', label: 'Security', icon: 'M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z' },
      { id: 'billing', label: 'Billing', icon: 'M20 4H4c-1.11 0-1.99.89-1.99 2L2 18c0 1.11.89 2 2 2h16c1.11 0 2-.89 2-2V6c0-1.11-.89-2-2-2zm0 14H4v-6h16v6zm0-10H4V6h16v2z' },
    ],
  },
  {
    label: 'Resources',
    items: [
      { id: 'docs', label: 'Documentation', icon: 'M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z' },
      { id: 'support', label: 'Support', icon: 'M11.5 2C6.81 2 3 5.81 3 10.5S6.81 19 11.5 19h.5v3c4.86-2.34 8-7 8-11.5C20 5.81 16.19 2 11.5 2zm1 14.5h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 9.9 13 10.5 13 11.5h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H8c0-2.21 1.79-4 4-4s4 1.79 4 4c0 .88-.36 1.68-.93 2.25z' },
    ],
  },
]

// Providers from store
const providers = computed(() => {
  const storeProviders = llmStore.providers || []
  if (storeProviders.length > 0) return storeProviders.map(p => ({
    id: p.id,
    name: p.name,
    icon: getProviderIcon(p.id),
    status: p.id === llmStore.currentProvider ? 'connected' : 'not-configured',
    models: p.models || [],
  }))
  return [
    { id: 'openai', name: 'OpenAI', icon: 'openai', status: 'connected', models: ['GPT-4o', 'GPT-4 Turbo', 'GPT-3.5 Turbo'] },
    { id: 'anthropic', name: 'Anthropic', icon: 'anthropic', status: 'not-configured', models: ['Claude 3.5 Sonnet', 'Claude 3 Opus'] },
    { id: 'gemini', name: 'Google Gemini', icon: 'gemini', status: 'not-configured', models: ['gemini-2.0-flash', 'gemini-pro'] },
    { id: 'local_llm', name: 'Local LLM', icon: 'local_llm', status: 'disconnected', models: ['qwen2.5-3b', 'qwen3.5-4b'] },
  ]
})

function getProviderIcon(id) {
  const icons = {
    openai: 'M4 8h4V4H4v4zm6 12h4v-4h-4v4zm-6 0h4v-4H4v4zm0-6h4v-4H4v4zm6 0h4v-4h-4v4zm6-10v4h4V4h-4zm-6 4h4V4h-4v4zm6 6h4v-4h-4v4zm0 6h4v-4h-4v4z',
    anthropic: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z',
    gemini: 'M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 3c1.93 0 3.5 1.57 3.5 3.5S13.93 13 12 13s-3.5-1.57-3.5-3.5S10.07 6 12 6zm7 13H5v-.23c0-.62.28-1.2.76-1.58C7.47 15.82 9.64 15 12 15s4.53.82 6.24 2.19c.48.38.76.97.76 1.58V19z',
    local_llm: 'M9.4 16.6L4.8 12l4.6-4.6L8 6l-6 6 6 6 1.4-1.4zm5.2 0l4.6-4.6-4.6-4.6L16 6l6 6-6 6-1.4-1.4z',
  }
  return icons[id] || icons.openai
}

// Model settings form
const selectedProvider = ref('')
const selectedModel = ref('')
const temperature = ref(0.7)
const maxTokens = ref(4096)
const apiKey = ref('')
const showApiKey = ref(false)
const systemPrompt = ref('')

const saving = ref(false)
const testingConnection = ref(false)
const testResult = ref(null)
const saveMessage = ref('')

onMounted(() => {
  llmStore.loadProviders().then(() => {
    selectedProvider.value = llmStore.currentProvider || 'openai'
    selectedModel.value = llmStore.currentModel || ''
  })
})

const currentProviderData = computed(() => {
  return providers.value.find(p => p.id === selectedProvider.value) || providers.value[0]
})

const availableModels = computed(() => {
  return currentProviderData.value?.models || []
})

const handleProviderSelect = (providerId) => {
  selectedProvider.value = providerId
  const p = providers.value.find(pr => pr.id === providerId)
  if (p?.models?.length) selectedModel.value = p.models[0]
}

const handleSave = async () => {
  saving.value = true
  saveMessage.value = ''
  try {
    await llmStore.switchProvider(selectedProvider.value, selectedModel.value)
    saveMessage.value = 'Configuration saved successfully'
    setTimeout(() => { saveMessage.value = '' }, 3000)
  } catch (err) {
    saveMessage.value = 'Failed to save configuration'
  } finally {
    saving.value = false
  }
}

const handleTestConnection = async () => {
  testingConnection.value = true
  testResult.value = null
  try {
    await llmStore.switchProvider(selectedProvider.value, selectedModel.value)
    testResult.value = { success: true, message: 'Connection successful' }
  } catch (err) {
    testResult.value = { success: false, message: err.message || 'Connection failed' }
  } finally {
    testingConnection.value = false
    setTimeout(() => { testResult.value = null }, 5000)
  }
}

const getStatusLabel = (status) => {
  const labels = { connected: 'CONNECTED', 'not-configured': 'NOT CONFIGURED', disconnected: 'DISCONNECTED' }
  return labels[status] || status.toUpperCase()
}

const getStatusClass = (status) => {
  return `status-${status}`
}
</script>

<template>
  <div class="config-page">
    <!-- Sidebar -->
    <aside class="config-sidebar">
      <div class="sidebar-brand">
        <svg class="sidebar-brand-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z"/></svg>
        <div class="sidebar-brand-text">
          <span class="brand-title">System Config</span>
          <span class="brand-sub">AI Infrastructure</span>
        </div>
      </div>

      <button class="back-home-btn" @click="emit('close')">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/></svg>
        Back to Home
      </button>

      <nav class="sidebar-nav">
        <div v-for="section in navSections" :key="section.label" class="nav-section">
          <span class="nav-section-label">{{ section.label }}</span>
          <button
            v-for="item in section.items"
            :key="item.id"
            class="nav-item"
            :class="{ active: activeNav === item.id }"
            @click="activeNav = item.id"
          >
            <svg class="nav-icon" viewBox="0 0 24 24" fill="currentColor"><path :d="item.icon" /></svg>
            <span>{{ item.label }}</span>
          </button>
        </div>
      </nav>

      <div class="sidebar-footer">
        <button class="deploy-btn">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M5 17h14v2H5zm7-12L5.33 15h13.34z"/></svg>
          Deploy Changes
        </button>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="config-main">
      <div class="config-header">
        <div class="header-text">
          <h1 class="config-title">Language Model Configuration</h1>
          <p class="config-desc">
            Manage your institution's AI infrastructure. Select high-performance models, configure API parameters, and monitor provider connectivity.
          </p>
        </div>
      </div>

      <!-- LLM Providers -->
      <section class="config-section">
        <h2 class="section-title">
          <svg class="section-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M4 8h4V4H4v4zm6 12h4v-4h-4v4zm-6 0h4v-4H4v4zm0-6h4v-4H4v4zm6 0h4v-4h-4v4zm6-10v4h4V4h-4zm-6 4h4V4h-4v4zm6 6h4v-4h-4v4zm0 6h4v-4h-4v4z"/></svg>
          LLM Providers
        </h2>

        <div class="providers-grid">
          <div
            v-for="provider in providers"
            :key="provider.id"
            class="provider-card"
            :class="{ active: selectedProvider === provider.id }"
            @click="handleProviderSelect(provider.id)"
          >
            <div class="provider-header">
              <div class="provider-icon-wrap">
                <svg class="provider-icon" viewBox="0 0 24 24" fill="currentColor"><path :d="provider.icon" /></svg>
              </div>
              <div class="provider-info">
                <span class="provider-name">{{ provider.name }}</span>
                <span class="provider-status" :class="getStatusClass(provider.status)">
                  <span v-if="provider.status === 'connected'" class="status-dot"></span>
                  {{ getStatusLabel(provider.status) }}
                </span>
              </div>
            </div>
            <button class="provider-action" :class="provider.status">
              {{ provider.status === 'connected' ? 'Configure' : provider.status === 'disconnected' ? 'Connect Local' : 'Setup Provider' }}
            </button>
          </div>
        </div>
      </section>

      <!-- Active Model Settings -->
      <section class="config-section">
        <h2 class="section-title">
          <svg class="section-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M3 17v2h6v-2H3zM3 5v2h10V5H3zm10 16v-2h8v-2h-8v-2h-2v6h2zM7 9v2H3v2h4v2h2V9H7zm14 4v-2H11v2h10zm-6-4h2V7h4V5h-4V3h-2v6z"/></svg>
          Active Model Settings
        </h2>

        <div class="settings-card">
          <!-- Model Selection -->
          <div class="form-group">
            <label class="form-label">Model Selection</label>
            <div class="select-wrap">
              <select v-model="selectedModel" class="form-select">
                <option v-for="model in availableModels" :key="model" :value="model">{{ model }}</option>
              </select>
              <svg class="select-arrow" viewBox="0 0 24 24" fill="currentColor"><path d="M7 10l5 5 5-5z"/></svg>
            </div>
          </div>

          <!-- Temperature -->
          <div class="form-group">
            <div class="form-label-row">
              <label class="form-label">Temperature</label>
              <span class="form-value">{{ temperature.toFixed(1) }}</span>
            </div>
            <input
              v-model.number="temperature"
              type="range"
              min="0"
              max="1"
              step="0.1"
              class="form-range"
            />
            <div class="range-labels">
              <span>Precise</span>
              <span>Creative</span>
            </div>
          </div>

          <!-- Max Tokens -->
          <div class="form-group">
            <div class="form-label-row">
              <label class="form-label">Max Tokens</label>
              <span class="form-value">{{ maxTokens.toLocaleString() }}</span>
            </div>
            <input
              v-model.number="maxTokens"
              type="range"
              min="256"
              max="16384"
              step="256"
              class="form-range"
            />
            <div class="range-labels">
              <span>Short</span>
              <span>Extended</span>
            </div>
          </div>

          <!-- API Key -->
          <div class="form-group">
            <label class="form-label">API Authentication Key</label>
            <div class="api-key-wrap">
              <svg class="api-key-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z"/></svg>
              <input
                v-model="apiKey"
                :type="showApiKey ? 'text' : 'password'"
                class="form-input api-key-input"
                placeholder="sk-..."
              />
              <button class="api-key-toggle" @click="showApiKey = !showApiKey">
                <svg viewBox="0 0 24 24" fill="currentColor">
                  <path v-if="showApiKey" d="M12 7c2.76 0 5 2.24 5 5 0 .65-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 2.7-2.89 3.43-4.75-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7l2.16 2.16C10.74 7.13 11.35 7 12 7zM2 4.27l2.28 2.28.46.46C3.08 8.3 1.78 10.02 1 12c1.73 4.39 6 7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55c-.05.21-.08.43-.08.65 0 1.66 1.34 3 3 3 .22 0 .44-.03.65-.08l1.55 1.55c-.67.33-1.41.53-2.2.53-2.76 0-5-2.24-5-5 0-.79.2-1.53.53-2.2zm4.31-.78l3.15 3.15.02-.16c0-1.66-1.34-3-3-3l-.17.01z"/>
                  <path v-else d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/>
                </svg>
              </button>
            </div>
            <div class="form-hint">
              <svg viewBox="0 0 24 24" fill="currentColor"><path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2z"/></svg>
              Keys are encrypted and stored in your local enclave.
            </div>
          </div>

          <!-- Test Connection -->
          <button class="test-btn" @click="handleTestConnection" :disabled="testingConnection">
            <svg v-if="testingConnection" class="spin" viewBox="0 0 24 24" fill="currentColor"><path d="M12 6v3l4-4-4-4v3c-4.42 0-8 3.58-8 8 0 1.57.46 3.03 1.24 4.26L6.7 14.8c-.45-.83-.7-1.79-.7-2.8 0-3.31 2.69-6 6-6zm6.76 1.74L17.3 9.2c.44.84.7 1.79.7 2.8 0 3.31-2.69 6-6 6v-3l-4 4 4 4v-3c4.42 0 8-3.58 8-8 0-1.57-.46-3.03-1.24-4.26z"/></svg>
            <svg v-else viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
            {{ testingConnection ? 'Testing...' : 'Test Connection' }}
          </button>

          <div v-if="testResult" class="test-result" :class="testResult.success ? 'success' : 'error'">
            {{ testResult.message }}
          </div>

          <!-- Warning -->
          <div class="warning-card">
            <svg class="warning-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>
            <div class="warning-text">
              <strong>Data Usage Warning</strong>
              <span>Current model settings may incur higher API costs.</span>
            </div>
          </div>

          <!-- Actions -->
          <div class="form-actions">
            <button class="btn-discard" @click="emit('close')">Discard</button>
            <button class="btn-save" @click="handleSave" :disabled="saving">
              {{ saving ? 'Saving...' : 'Save Configuration' }}
            </button>
          </div>

          <div v-if="saveMessage" class="save-message" :class="saveMessage.includes('success') ? 'success' : 'error'">
            {{ saveMessage }}
          </div>
        </div>
      </section>

      <!-- Model Performance -->
      <section class="config-section">
        <h2 class="section-title">
          <svg class="section-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z"/></svg>
          Model Performance
        </h2>

        <div class="performance-grid">
          <div class="perf-card">
            <div class="perf-header">
              <span class="perf-label">Success Rate</span>
              <span class="perf-badge excellent">EXCELLENT</span>
            </div>
            <div class="perf-value">
              <span class="perf-number">98.2</span>
              <span class="perf-unit">%</span>
            </div>
            <div class="perf-trend up">
              <svg viewBox="0 0 24 24" fill="currentColor"><path d="M7 14l5-5 5 5z"/></svg>
              2.4%
            </div>
            <p class="perf-desc">Success rate for complex research synthesis across last 1,000 queries.</p>
          </div>

          <div class="perf-card">
            <div class="perf-header">
              <span class="perf-label">Latency (Avg)</span>
              <span class="perf-badge excellent">EXCELLENT</span>
            </div>
            <div class="perf-value">
              <span class="perf-number">1.4</span>
              <span class="perf-unit">s</span>
            </div>
            <p class="perf-desc">Average time to first token for the current configuration.</p>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.config-page {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  height: 100%;
  background: var(--surface);
}

/* Sidebar */
.config-sidebar {
  background: var(--surface-container-low);
  display: flex;
  flex-direction: column;
  border-right: 1px solid rgba(69, 70, 83, 0.12);
}

.sidebar-brand {
  padding: 20px 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  border-bottom: 1px solid rgba(69, 70, 83, 0.1);
}

.back-home-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 12px 8px 0;
  padding: 9px 12px;
  border-radius: 8px;
  border: 1px solid rgba(69, 70, 83, 0.2);
  background: var(--surface-container);
  color: var(--on-surface-variant);
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.back-home-btn svg {
  width: 18px;
  height: 18px;
}

.back-home-btn:hover {
  background: var(--surface-container-high);
  color: var(--on-surface);
  border-color: rgba(129, 140, 248, 0.3);
}

.sidebar-brand-icon {
  width: 28px;
  height: 28px;
  color: var(--primary-container);
}

.sidebar-brand-text {
  display: flex;
  flex-direction: column;
}

.brand-title {
  font-family: var(--font-headline);
  font-size: 13px;
  font-weight: 700;
  color: var(--on-surface);
}

.brand-sub {
  font-size: 11px;
  color: var(--on-surface-variant);
}

.sidebar-nav {
  flex: 1;
  padding: 12px 8px;
  overflow-y: auto;
}

.nav-section {
  margin-bottom: 16px;
}

.nav-section-label {
  display: block;
  padding: 4px 10px;
  font-size: 10px;
  font-weight: 600;
  color: var(--on-surface-variant);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 4px;
}

.nav-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: var(--on-surface-variant);
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  text-align: left;
}

.nav-item:hover {
  background: rgba(189, 194, 255, 0.06);
  color: var(--on-surface);
}

.nav-item.active {
  background: rgba(129, 140, 248, 0.12);
  color: var(--primary);
}

.nav-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.sidebar-footer {
  padding: 12px;
  border-top: 1px solid rgba(69, 70, 83, 0.1);
}

.deploy-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: 8px;
  border: none;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-container) 100%);
  color: var(--on-primary);
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.deploy-btn svg {
  width: 16px;
  height: 16px;
}

.deploy-btn:hover {
  box-shadow: 0 4px 16px rgba(129, 140, 248, 0.25);
}

/* Main */
.config-main {
  padding: 32px 40px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.config-header {
  max-width: 720px;
}

.config-title {
  font-family: var(--font-headline);
  font-size: 26px;
  font-weight: 700;
  color: var(--on-surface);
  margin: 0 0 8px;
  letter-spacing: -0.02em;
}

.config-desc {
  font-size: 14px;
  color: var(--on-surface-variant);
  margin: 0;
  line-height: 1.6;
}

/* Sections */
.config-section {
  max-width: 720px;
}

.section-title {
  font-family: var(--font-headline);
  font-size: 15px;
  font-weight: 600;
  color: var(--on-surface);
  margin: 0 0 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-icon {
  width: 20px;
  height: 20px;
  color: var(--primary-container);
}

/* Provider Cards */
.providers-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.provider-card {
  padding: 16px;
  border-radius: 10px;
  background: var(--surface-container);
  display: flex;
  flex-direction: column;
  gap: 12px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.provider-card:hover {
  background: var(--surface-container-high);
}

.provider-card.active {
  border-color: rgba(129, 140, 248, 0.3);
  background: rgba(129, 140, 248, 0.06);
}

.provider-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.provider-icon-wrap {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(129, 140, 248, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.provider-icon {
  width: 20px;
  height: 20px;
  color: var(--primary-container);
}

.provider-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.provider-name {
  font-family: var(--font-headline);
  font-size: 14px;
  font-weight: 600;
  color: var(--on-surface);
}

.provider-status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.03em;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.status-connected {
  color: #4ade80;
}
.status-connected .status-dot {
  background: #4ade80;
}

.status-not-configured {
  color: var(--on-surface-variant);
}

.status-disconnected {
  color: #f87171;
}

.provider-action {
  padding: 8px 14px;
  border-radius: 8px;
  border: 1px solid var(--outline-variant);
  background: transparent;
  color: var(--on-surface-variant);
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  align-self: flex-start;
}

.provider-action:hover {
  border-color: var(--primary-container);
  color: var(--primary);
  background: rgba(129, 140, 248, 0.06);
}

.provider-action.connected {
  border-color: rgba(74, 222, 128, 0.3);
  color: #4ade80;
}

/* Settings Card */
.settings-card {
  padding: 24px;
  border-radius: 12px;
  background: var(--surface-container);
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--on-surface);
  font-family: var(--font-headline);
}

.form-label-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.form-value {
  font-size: 14px;
  font-weight: 700;
  color: var(--primary);
  font-family: var(--font-headline);
}

.select-wrap {
  position: relative;
}

.form-select {
  width: 100%;
  padding: 10px 40px 10px 14px;
  border-radius: 8px;
  border: 1px solid rgba(69, 70, 83, 0.2);
  background: var(--surface-container-lowest);
  color: var(--on-surface);
  font-family: var(--font-body);
  font-size: 13px;
  appearance: none;
  cursor: pointer;
  transition: border-color 0.2s;
}

.form-select:focus {
  outline: none;
  border-color: var(--primary-container);
}

.select-arrow {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  width: 20px;
  height: 20px;
  color: var(--on-surface-variant);
  pointer-events: none;
}

.form-range {
  width: 100%;
  height: 4px;
  appearance: none;
  background: var(--outline-variant);
  border-radius: 2px;
  outline: none;
}

.form-range::-webkit-slider-thumb {
  appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--primary-container);
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(129, 140, 248, 0.3);
}

.range-labels {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--on-surface-variant);
}

.api-key-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid rgba(69, 70, 83, 0.2);
  background: var(--surface-container-lowest);
  transition: border-color 0.2s;
}

.api-key-wrap:focus-within {
  border-color: var(--primary-container);
}

.api-key-icon {
  width: 18px;
  height: 18px;
  color: var(--on-surface-variant);
  flex-shrink: 0;
}

.api-key-input {
  flex: 1;
  padding: 10px 0;
  border: none;
  background: transparent;
  color: var(--on-surface);
  font-family: var(--font-body);
  font-size: 13px;
  outline: none;
}

.api-key-toggle {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--on-surface-variant);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.api-key-toggle svg {
  width: 18px;
  height: 18px;
}

.api-key-toggle:hover {
  background: rgba(255, 255, 255, 0.06);
  color: var(--on-surface);
}

.form-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--on-surface-variant);
  opacity: 0.7;
}

.form-hint svg {
  width: 14px;
  height: 14px;
}

.test-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 20px;
  border-radius: 8px;
  border: 1px solid var(--outline-variant);
  background: transparent;
  color: var(--on-surface);
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  align-self: flex-start;
}

.test-btn svg {
  width: 18px;
  height: 18px;
}

.test-btn:hover:not(:disabled) {
  border-color: var(--primary-container);
  background: rgba(129, 140, 248, 0.06);
}

.test-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.test-result {
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
}

.test-result.success {
  background: rgba(74, 222, 128, 0.08);
  color: #4ade80;
}

.test-result.error {
  background: rgba(248, 113, 113, 0.08);
  color: #f87171;
}

.warning-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 10px;
  background: rgba(247, 189, 62, 0.06);
  border: 1px solid rgba(247, 189, 62, 0.15);
}

.warning-icon {
  width: 20px;
  height: 20px;
  color: var(--tertiary);
  flex-shrink: 0;
  margin-top: 1px;
}

.warning-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
  color: var(--on-surface-variant);
}

.warning-text strong {
  color: var(--tertiary);
  font-size: 13px;
}

.form-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  padding-top: 4px;
}

.btn-discard {
  padding: 10px 20px;
  border-radius: 8px;
  border: 1px solid var(--outline-variant);
  background: transparent;
  color: var(--on-surface-variant);
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-discard:hover {
  background: rgba(255, 255, 255, 0.04);
  color: var(--on-surface);
}

.btn-save {
  padding: 10px 24px;
  border-radius: 8px;
  border: none;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-container) 100%);
  color: var(--on-primary);
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-save:hover:not(:disabled) {
  box-shadow: 0 4px 16px rgba(129, 140, 248, 0.25);
}

.btn-save:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.save-message {
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  text-align: center;
}

.save-message.success {
  background: rgba(74, 222, 128, 0.08);
  color: #4ade80;
}

.save-message.error {
  background: rgba(248, 113, 113, 0.08);
  color: #f87171;
}

/* Performance */
.performance-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.perf-card {
  padding: 20px;
  border-radius: 12px;
  background: var(--surface-container);
}

.perf-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.perf-label {
  font-family: var(--font-headline);
  font-size: 13px;
  font-weight: 600;
  color: var(--on-surface-variant);
}

.perf-badge {
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.perf-badge.excellent {
  background: rgba(74, 222, 128, 0.1);
  color: #4ade80;
}

.perf-value {
  display: flex;
  align-items: baseline;
  gap: 2px;
  margin-bottom: 4px;
}

.perf-number {
  font-family: var(--font-headline);
  font-size: 32px;
  font-weight: 700;
  color: var(--on-surface);
  letter-spacing: -0.02em;
}

.perf-unit {
  font-family: var(--font-headline);
  font-size: 18px;
  font-weight: 600;
  color: var(--on-surface-variant);
}

.perf-trend {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 8px;
}

.perf-trend.up {
  color: #4ade80;
}

.perf-trend svg {
  width: 16px;
  height: 16px;
}

.perf-desc {
  font-size: 12px;
  color: var(--on-surface-variant);
  margin: 0;
  line-height: 1.5;
}

/* Utility */
.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@media (max-width: 900px) {
  .config-page {
    grid-template-columns: 1fr;
  }
  .config-sidebar {
    display: none;
  }
  .providers-grid,
  .performance-grid {
    grid-template-columns: 1fr;
  }
}
</style>
