import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { 
  getEmbeddingModels, 
  getCurrentEmbeddingModel, 
  switchEmbeddingModel,
  testEmbeddingModel 
} from '../services/api'

// Available embedding models with metadata
const AVAILABLE_MODELS = [
  {
    id: 'sentence-transformers/all-MiniLM-L6-v2',
    name: 'MiniLM (L6-v2)',
    dimension: 384,
    speed: 'Very Fast',
    memory: '~80 MB',
    description: 'Lightweight, fast model for general-purpose embeddings',
    recommended: true,
  },
  {
    id: 'BAAI/bge-small-en-v1.5',
    name: 'BGE-small',
    dimension: 384,
    speed: 'Fast',
    memory: '~120 MB',
    description: 'Small model with good retrieval performance',
    recommended: false,
  },
  {
    id: 'sentence-transformers/all-MiniLM-L12-v2',
    name: 'MiniLM (L12-v2)',
    dimension: 384,
    speed: 'Very Fast',
    memory: '~120 MB',
    description: '12-layer MiniLM with better accuracy than L6 variant',
    recommended: false,
  },
  {
    id: 'thenlper/gte-small',
    name: 'GTE-small',
    dimension: 384,
    speed: 'Very Fast',
    memory: '~70 MB',
    description: 'Alibaba GTE small model, strong MTEB score for its size',
    recommended: false,
  },
  {
    id: 'intfloat/e5-small-v2',
    name: 'E5-small',
    dimension: 384,
    speed: 'Very Fast',
    memory: '~130 MB',
    description: 'Microsoft E5 small model for efficient text retrieval',
    recommended: false,
  },
  {
    id: 'Snowflake/snowflake-arctic-embed-s',
    name: 'Arctic-embed-s',
    dimension: 384,
    speed: 'Very Fast',
    memory: '~130 MB',
    description: 'Snowflake retrieval-optimized small model, SOTA for its size',
    recommended: false,
  },
  {
    id: 'nomic-ai/nomic-embed-text-v1.5',
    name: 'Nomic-embed-v1.5',
    dimension: 768,
    speed: 'Fast',
    memory: '~550 MB',
    description: '8K context model with Matryoshka flexible dimensions',
    recommended: false,
  },
  {
    id: 'BAAI/bge-large-en-v1.5',
    name: 'BGE-large',
    dimension: 1024,
    speed: 'Medium',
    memory: '~1.2 GB',
    description: 'Large model with excellent retrieval accuracy',
    recommended: false,
  },
  {
    id: 'intfloat/e5-large-v2',
    name: 'E5-large',
    dimension: 1024,
    speed: 'Medium',
    memory: '~1.3 GB',
    description: 'Microsoft E5 model for text embeddings',
    recommended: false,
  },
  {
    id: 'Qwen/Qwen3-Embedding-0.6B',
    name: 'Qwen3-0.6B',
    dimension: 1024,
    speed: 'Slow',
    memory: '~2.5 GB',
    description: 'Qwen3 large embedding model',
    recommended: false,
  },
  {
    id: 'sentence-transformers/all-mpnet-base-v2',
    name: 'MPNet-base',
    dimension: 768,
    speed: 'Medium',
    memory: '~420 MB',
    description: 'Strong all-around performance model',
    recommended: false,
  },
  {
    id: 'BAAI/bge-m3',
    name: 'BGE-M3',
    dimension: 1024,
    speed: 'Medium',
    memory: '~2.3 GB',
    description: 'Multilingual model with dense, sparse, and ColBERT retrieval',
    recommended: false,
  },
  {
    id: 'nvidia/NV-Embed-v2',
    name: 'NV-Embed-v2',
    dimension: 4096,
    speed: 'Very Slow',
    memory: '~15 GB',
    description: 'NVIDIA top-ranked MTEB model based on Mistral-7B',
    recommended: false,
  },
  {
    id: 'Qwen/Qwen3-Embedding-8B',
    name: 'Qwen3-8B',
    dimension: 4096,
    speed: 'Very Slow',
    memory: '~16 GB',
    description: 'Qwen3 8B embedding model with 32K context and MRL support',
    recommended: false,
  },
  {
    id: 'BAAI/bge-en-icl',
    name: 'BGE-en-ICL',
    dimension: 4096,
    speed: 'Very Slow',
    memory: '~14 GB',
    description: 'In-context learning retrieval model based on Mistral-7B',
    recommended: false,
  },
  {
    id: 'Alibaba-NLP/gte-Qwen2-7B-instruct',
    name: 'GTE-Qwen2-7B',
    dimension: 3584,
    speed: 'Very Slow',
    memory: '~26 GB',
    description: 'Alibaba GTE 7B instruct model for multilingual embeddings',
    recommended: false,
  },
]

export const useEmbeddingStore = defineStore('embedding', () => {
  // State
  const currentModel = ref(null)
  const availableModels = ref(AVAILABLE_MODELS)
  const isLoading = ref(false)
  const isSwitching = ref(false)
  const isTesting = ref(false)
  const error = ref(null)
  const lastTestResults = ref(null)
  const performanceMetrics = ref([])

  // Getters
  const currentModelInfo = computed(() => {
    if (!currentModel.value) return null
    return availableModels.value.find(m => m.id === currentModel.value.id) || currentModel.value
  })

  const isModelChanging = computed(() => isSwitching.value || isLoading.value)

  // Actions
  async function loadAvailableModels() {
    try {
      isLoading.value = true
      error.value = null
      const response = await getEmbeddingModels()
      if (response.models) {
        // Merge server models with local metadata
        availableModels.value = AVAILABLE_MODELS.map(local => {
          const server = response.models.find(m => m.id === local.id)
          return server ? { ...local, ...server } : local
        })
      }
    } catch (err) {
      error.value = err.message
      console.error('Failed to load embedding models:', err)
    } finally {
      isLoading.value = false
    }
  }

  async function loadCurrentModel() {
    try {
      isLoading.value = true
      error.value = null
      const response = await getCurrentEmbeddingModel()
      currentModel.value = {
        id: response.model_id || response.model,
        name: response.model_name || response.model,
        dimension: response.dimension,
        isLoaded: response.is_loaded,
      }
      
      // Save to localStorage
      localStorage.setItem('embedding_model', JSON.stringify(currentModel.value))
    } catch (err) {
      error.value = err.message
      console.error('Failed to load current embedding model:', err)
      // Try to restore from localStorage
      const saved = localStorage.getItem('embedding_model')
      if (saved) {
        try {
          currentModel.value = JSON.parse(saved)
        } catch (e) {
          console.error('Failed to restore model from localStorage:', e)
        }
      }
    } finally {
      isLoading.value = false
    }
  }

  async function switchModel(modelId, options = {}) {
    const { reindex = false, onProgress = null } = options
    
    if (!modelId) {
      error.value = 'Model ID is required'
      return false
    }

    try {
      isSwitching.value = true
      error.value = null

      const response = await switchEmbeddingModel(modelId, { reindex })
      
      if (response.success) {
        currentModel.value = {
          id: response.model_id,
          name: response.model_name,
          dimension: response.dimension,
          isLoaded: true,
        }
        
        // Save to localStorage
        localStorage.setItem('embedding_model', JSON.stringify(currentModel.value))
        
        // Record performance metric
        recordPerformanceMetric('switch', modelId, response.load_time_ms)
        
        return true
      } else {
        throw new Error(response.error || 'Failed to switch model')
      }
    } catch (err) {
      error.value = err.message
      console.error('Failed to switch embedding model:', err)
      
      // Fallback: try to restore previous model
      const saved = localStorage.getItem('embedding_model')
      if (saved) {
        try {
          currentModel.value = JSON.parse(saved)
        } catch (e) {
          console.error('Failed to restore previous model:', e)
        }
      }
      return false
    } finally {
      isSwitching.value = false
    }
  }

  async function testModel(modelId, query = 'test query') {
    try {
      isTesting.value = true
      error.value = null
      
      const response = await testEmbeddingModel(modelId, { query })
      
      lastTestResults.value = {
        modelId,
        query,
        results: response.results || [],
        retrievalTimeMs: response.retrieval_time_ms,
        totalResults: response.total_results,
        timestamp: new Date().toISOString(),
      }
      
      // Record performance metric
      recordPerformanceMetric('test', modelId, response.retrieval_time_ms)
      
      return lastTestResults.value
    } catch (err) {
      error.value = err.message
      console.error('Failed to test embedding model:', err)
      return null
    } finally {
      isTesting.value = false
    }
  }

  function recordPerformanceMetric(action, modelId, timeMs) {
    performanceMetrics.value.unshift({
      action,
      modelId,
      timeMs,
      timestamp: new Date().toISOString(),
    })
    
    // Keep only last 100 metrics
    if (performanceMetrics.value.length > 100) {
      performanceMetrics.value = performanceMetrics.value.slice(0, 100)
    }
  }

  function getAverageRetrievalTime(modelId) {
    const metrics = performanceMetrics.value.filter(
      m => m.modelId === modelId && (m.action === 'switch' || m.action === 'test')
    )
    if (metrics.length === 0) return null
    const avg = metrics.reduce((sum, m) => sum + m.timeMs, 0) / metrics.length
    return Math.round(avg * 100) / 100
  }

  function clearError() {
    error.value = null
  }

  return {
    // State
    currentModel,
    availableModels,
    isLoading,
    isSwitching,
    isTesting,
    error,
    lastTestResults,
    performanceMetrics,
    // Getters
    currentModelInfo,
    isModelChanging,
    // Actions
    loadAvailableModels,
    loadCurrentModel,
    switchModel,
    testModel,
    recordPerformanceMetric,
    getAverageRetrievalTime,
    clearError,
  }
})
