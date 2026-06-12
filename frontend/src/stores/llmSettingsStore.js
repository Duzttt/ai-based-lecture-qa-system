import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getLlmHealth, getProviders, saveSettings } from '../services/api'

export const useLlmSettingsStore = defineStore('llmSettings', () => {
  const currentProvider = ref('')
  const currentModel = ref('')
  const providers = ref([])
  const isSwitching = ref(false)
  const error = ref(null)

  const currentProviderInfo = computed(() => {
    return providers.value.find(p => p.id === currentProvider.value) || null
  })

  const currentProviderName = computed(() => {
    return currentProviderInfo.value?.name || currentProvider.value
  })

  async function loadProviders() {
    try {
      error.value = null
      const data = await getProviders()
      currentProvider.value = data.current.provider
      currentModel.value = data.current.model
      providers.value = data.providers
    } catch (err) {
      error.value = err.message
      console.error('Failed to load LLM providers:', err)
    }
  }

  async function switchProvider(providerId, model) {
    const selectedModel = String(model || '').trim()
    if (!providerId || !selectedModel) {
      error.value = 'Provider and model are required'
      return false
    }

    try {
      isSwitching.value = true
      error.value = null

      const response = await saveSettings({
        llm_provider: providerId,
        model: selectedModel,
        api_key: '',
      })

      if (!response.success) {
        throw new Error(response.detail || response.message || 'Failed to switch provider')
      }

      currentProvider.value = providerId
      currentModel.value = selectedModel
      await loadProviders()
      return true
    } catch (err) {
      error.value = err.message
      console.error('Failed to switch LLM provider:', err)
      return false
    } finally {
      isSwitching.value = false
    }
  }

  async function testConnection(providerId, model) {
    const selectedProvider = providerId || currentProvider.value
    const selectedModel = String(model || currentModel.value || '').trim()

    if (!selectedProvider || !selectedModel) {
      const err = new Error('Provider and model are required')
      error.value = err.message
      throw err
    }

    if (selectedProvider !== 'local_llm') {
      return {
        status: 'ready',
        detail: 'Provider configuration is ready to save.',
      }
    }

    try {
      error.value = null
      const health = await getLlmHealth({
        provider: selectedProvider,
        model: selectedModel,
      })

      if (health.status !== 'healthy') {
        throw new Error(health.detail || 'llama.cpp connection failed')
      }

      return health
    } catch (err) {
      error.value = err.message
      console.error('Failed to test LLM connection:', err)
      throw err
    }
  }

  return {
    currentProvider,
    currentModel,
    providers,
    isSwitching,
    error,
    currentProviderInfo,
    currentProviderName,
    loadProviders,
    switchProvider,
    testConnection,
  }
})
