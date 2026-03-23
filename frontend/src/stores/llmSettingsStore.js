import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getProviders, saveSettings } from '../services/api'

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
    if (!providerId || !model) {
      error.value = 'Provider and model are required'
      return false
    }

    try {
      isSwitching.value = true
      error.value = null

      await saveSettings({
        llm_provider: providerId,
        model: model,
        api_key: '',
      })

      currentProvider.value = providerId
      currentModel.value = model
      return true
    } catch (err) {
      error.value = err.message
      console.error('Failed to switch LLM provider:', err)
      return false
    } finally {
      isSwitching.value = false
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
  }
})
