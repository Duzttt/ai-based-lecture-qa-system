import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

export const uploadPDF = async (file, onProgress) => {
  const formData = new FormData()
  formData.append('file', file)
  
  const response = await api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (progressEvent) => {
      if (onProgress) {
        const percentCompleted = Math.round(
          (progressEvent.loaded * 100) / progressEvent.total
        )
        onProgress(percentCompleted)
      }
    },
  })
  
  return response.data
}

export const askQuestion = async (question) => {
  const response = await api.post('/chat', { query: question })
  return response.data
}

export const getSettings = async () => {
  const response = await api.get('/settings')
  return response.data
}

export const saveSettings = async (settings) => {
  const response = await api.post('/settings', {
    provider: settings.llm_provider,
    model: settings.model,
    api_key: settings.api_key,
  })
  return response.data
}

export const getProviders = async () => {
  const response = await api.get('/settings/providers')
  return response.data
}

export const getRagConfig = async () => {
  const response = await api.get('/rag-config')
  return response.data
}

export const updateRagConfig = async (config) => {
  const response = await api.post('/rag-config/update', config)
  return response.data
}

export const resetIndex = async () => {
  const response = await api.post('/index/reset')
  return response.data
}

export const getFiles = async () => {
  const response = await api.get('/files')
  return response.data
}

export const deleteFile = async (filename) => {
  const response = await api.post('/documents/delete', { filename })
  return response.data
}

export const compareDocuments = async (query, sources) => {
  const response = await api.post('/compare', { query, sources })
  return response.data
}

// Dashboard API
export const getDashboardStats = async () => {
  const response = await api.get('/dashboard/stats')
  return response.data
}

export const getDashboardMetrics = async () => {
  const response = await api.get('/dashboard/metrics')
  return response.data
}

export const getDashboardChunksDistribution = async () => {
  const response = await api.get('/dashboard/chunks/distribution')
  return response.data
}

export const getDashboardSimilarityDistribution = async () => {
  const response = await api.get('/dashboard/similarity/distribution')
  return response.data
}

export const getDashboardDocumentsTimeline = async () => {
  const response = await api.get('/dashboard/documents/timeline')
  return response.data
}

export const reindexDocuments = async () => {
  const response = await api.post('/dashboard/reindex')
  return response.data
}

// Embedding Model API
export const getEmbeddingModels = async () => {
  const response = await api.get('/settings/embedding-models')
  return response.data
}

export const getCurrentEmbeddingModel = async () => {
  const response = await api.get('/settings/embedding-model')
  return response.data
}

export const switchEmbeddingModel = async (modelId, options = {}) => {
  const response = await api.post('/settings/embedding-model/switch', {
    model_id: modelId,
    reindex: options.reindex || false,
  })
  return response.data
}

export const testEmbeddingModel = async (modelId, options = {}) => {
  const response = await api.post('/settings/embedding-model/test', {
    model_id: modelId,
    query: options.query || 'test query',
    top_k: options.top_k || 3,
  })
  return response.data
}

export const getEmbeddingModelMetrics = async () => {
  const response = await api.get('/settings/embedding-model/metrics')
  return response.data
}

export const clearEmbeddingModelCache = async () => {
  const response = await api.post('/settings/embedding-model/cache/clear')
  return response.data
}

// Document Summary API
export const generateSummary = async (documentIds, config = {}) => {
  const response = await api.post('/summary/generate', {
    document_ids: documentIds,
    config,
  })
  return response.data
}

export const getSummaryHistory = async (limit = 20) => {
  const response = await api.get(`/summary/history?limit=${limit}`)
  return response.data
}

export const deleteSummary = async (summaryId) => {
  const response = await api.post(`/summary/${summaryId}/delete`)
  return response.data
}

export const regenerateSummary = async (historyId, config = {}) => {
  const response = await api.post('/summary/regenerate', {
    history_id: historyId,
    config,
  })
  return response.data
}

// Question Suggestions API
export const getQuestionSuggestions = async (documentIds, numSuggestions = 3) => {
  const docIdsParam = documentIds.join(',')
  const response = await api.get(
    `/suggestions?doc_ids=${encodeURIComponent(docIdsParam)}&num_suggestions=${numSuggestions}`
  )
  return response.data
}

export const recordSuggestionClick = async (question, documentIds, position = 0) => {
  const response = await api.post('/suggestions/click', {
    question,
    doc_ids: documentIds,
    position,
  })
  return response.data
}

export const getSuggestionHistory = async (limit = 20, docId = '') => {
  const params = new URLSearchParams()
  if (limit) params.append('limit', limit)
  if (docId) params.append('doc_id', docId)
  
  const response = await api.get(`/suggestions/history?${params.toString()}`)
  return response.data
}

// Admin Dashboard API (Phase 1)
export const getAdminStats = async () => {
  const response = await api.get('/admin/stats')
  return response.data
}

export const getAdminQueryStats = async (hours = 24) => {
  const response = await api.get(`/admin/query-stats?hours=${hours}`)
  return response.data
}

export const debugRetrieval = async (query, params = {}) => {
  const response = await api.post('/admin/debug/retrieval', {
    query,
    params,
  })
  return response.data
}

export const getAdminDocuments = async (search = '') => {
  const url = search ? `/admin/documents?search=${encodeURIComponent(search)}` : '/admin/documents'
  const response = await api.get(url)
  return response.data
}

export const getAdminDocumentChunks = async (docId, page = 1, pageSize = 20) => {
  const response = await api.get(`/admin/documents/${encodeURIComponent(docId)}/chunks?page=${page}&page_size=${pageSize}`)
  return response.data
}

export const deleteAdminDocument = async (docId) => {
  const response = await api.post(`/admin/documents/${encodeURIComponent(docId)}/delete`)
  return response.data
}

export const reindexAdminDocument = async (docId) => {
  const response = await api.post(`/admin/documents/${encodeURIComponent(docId)}/reindex`)
  return response.data
}

export const getAdminIndexingStatus = async () => {
  const response = await api.get('/admin/indexing-status')
  return response.data
}

// Admin Analytics API (Phase 2)
export const getAdminDocumentAnalytics = async (docId) => {
  const response = await api.get(`/admin/analytics/document/${encodeURIComponent(docId)}`)
  return response.data
}

export const getAdminQueryClusters = async (days = 30, limit = 1000) => {
  const response = await api.get(`/admin/analytics/query-clusters?days=${days}&limit=${limit}`)
  return response.data
}

export const getAdminFailureAnalysis = async (timeRange = 24) => {
  const response = await api.get(`/admin/analytics/failures?time_range=${timeRange}`)
  return response.data
}

export const getAdminEmbeddingVisualization = async (method = 'pca', perplexity = 30, sampleSize = 500) => {
  const response = await api.get(`/admin/visualization/embeddings?method=${method}&perplexity=${perplexity}&sample_size=${sampleSize}`)
  return response.data
}

export const getAdminChunkQuality = async () => {
  const response = await api.get('/admin/analytics/chunk-quality')
  return response.data
}

export const traceRetrieval = async (query, topK = 5) => {
  const response = await api.post('/admin/debug/trace', {
    query,
    top_k: topK,
  })
  return response.data
}

// A/B Testing API
export const getABTests = async () => {
  const response = await api.get('/admin/abtests')
  return response.data
}

export const createABTest = async (testData) => {
  const response = await api.post('/admin/abtest/create', testData)
  return response.data
}

export const startABTest = async (testId) => {
  const response = await api.post(`/admin/abtest/${testId}/start`)
  return response.data
}

export const stopABTest = async (testId) => {
  const response = await api.post(`/admin/abtest/${testId}/stop`)
  return response.data
}

export const recordABTest = async (testId, variant, metrics) => {
  const response = await api.post('/admin/abtest/record', {
    test_id: testId,
    variant,
    metrics,
  })
  return response.data
}

export const getABTestResults = async (testId) => {
  const response = await api.get(`/admin/abtest/${testId}/results`)
  return response.data
}

// Phase 3: Smart Operations API
export const getCurrentAlerts = async () => {
  const response = await api.get('/admin/alerts/current')
  return response.data
}

export const acknowledgeAlert = async (alertId, action = 'acknowledge') => {
  const response = await api.post('/admin/alerts/acknowledge', {
    alert_id: alertId,
    action,
  })
  return response.data
}

export const getCapacityForecast = async (months = 3) => {
  const response = await api.get(`/admin/capacity/forecast?months=${months}`)
  return response.data
}

export const getSelfHealingEvents = async () => {
  const response = await api.get('/admin/selfhealing/events')
  return response.data
}

export const updateSelfHealingConfig = async (policies) => {
  const response = await api.put('/admin/selfhealing/config', { policies })
  return response.data
}

export const getCostAnalysis = async (month = '') => {
  const url = month ? `/admin/cost/analysis?month=${month}` : '/admin/cost/analysis'
  const response = await api.get(url)
  return response.data
}

export const getUserBehavior = async (period = 7) => {
  const response = await api.get(`/admin/analytics/users?period=${period}`)
  return response.data
}

export const generateReport = async (reportData) => {
  const response = await api.post('/admin/reports/generate', reportData)
  return response.data
}

export const getReportsHistory = async () => {
  const response = await api.get('/admin/reports/history')
  return response.data
}

export const getHealthScore = async () => {
  const response = await api.get('/admin/health/score')
  return response.data
}

export default api
