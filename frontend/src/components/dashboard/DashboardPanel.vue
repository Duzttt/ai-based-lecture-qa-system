<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { getDashboardStats, getDashboardMetrics, getDashboardChunksDistribution, getDashboardSimilarityDistribution, getDashboardDocumentsTimeline, updateRagConfig, reindexDocuments } from '../../services/api'
import DashboardHeader from './DashboardHeader.vue'
import IndexingProgress from './IndexingProgress.vue'
import DashboardStats from './DashboardStats.vue'
import DashboardCharts from './DashboardCharts.vue'
import DashboardConfig from './DashboardConfig.vue'

const emit = defineEmits(['close'])

// Stats data
const stats = ref({
  documents: { total: 0, total_pages: 0, total_chunks: 0 },
  vectors: { dimension: 384, index_type: 'IndexFlatL2', total_vectors: 0 },
  storage: { faiss_index_size_kb: 0, documents_size_kb: 0 },
})

const metrics = ref({
  embedding_time_ms: 0,
  retrieval_time_ms: 0,
  avg_similarity_score: 0,
})

const chunksDistribution = ref({ labels: [], data: [] })
const similarityDistribution = ref({ labels: [], data: [] })
const documentsTimeline = ref({ labels: [], data: [] })

// Config
const config = ref({
  chunk_size: 400,
  chunk_overlap: 50,
  embedding_model: 'sentence-transformers/all-MiniLM-L6-v2',
  top_k: 3,
  temperature: 0.7,
})

// WebSocket
let ws = null
const wsConnected = ref(false)
const indexingStatus = ref({ status: 'idle', progress: 0, current_file: '' })

// Loading states
const loading = ref(true)
const reindexing = ref(false)
const savingConfig = ref(false)

const loadDashboardData = async () => {
  try {
    const [statsData, metricsData, chunksData, similarityData, timelineData] = await Promise.all([
      getDashboardStats(),
      getDashboardMetrics(),
      getDashboardChunksDistribution(),
      getDashboardSimilarityDistribution(),
      getDashboardDocumentsTimeline()
    ])

    stats.value = statsData
    // Map backend metrics structure to frontend shape
    metrics.value = {
      retrieval_time_ms: metricsData?.performance?.avg_retrieval_time_ms ?? 0,
      embedding_time_ms: metricsData?.performance?.avg_embedding_time_ms ?? 0,
      // Use similarity distribution mean if available, otherwise 0
      avg_similarity_score: similarityData?.statistics?.mean ?? 0,
    }

    // Map chunks distribution (histogram -> labels/data)
    const chunkHist = chunksData?.histogram ?? []
    chunksDistribution.value = {
      labels: chunkHist.map((b) => b.range),
      data: chunkHist.map((b) => b.count),
    }

    // Map similarity distribution
    const simHist = similarityData?.histogram ?? []
    similarityDistribution.value = {
      labels: simHist.map((b) => b.range),
      data: simHist.map((b) => b.count),
    }

    // Map documents timeline (use display_name/name as label)
    const docs = timelineData?.documents ?? []
    documentsTimeline.value = {
      labels: docs.map((d) => d.display_name || d.name),
      // Simple sequence for now; could also use size or timestamp-derived metric
      data: docs.map((_, idx) => docs.length - idx),
    }
  } catch (err) {
    console.error('Failed to load dashboard data:', err)
  } finally {
    loading.value = false
  }
}

const connectWebSocket = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  ws = new WebSocket(`${protocol}//${window.location.host}/ws/dashboard/`)

  ws.onopen = () => {
    wsConnected.value = true
  }

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    if (data.type === 'indexing_status' || data.type === 'indexing_progress') {
      indexingStatus.value = {
        status: data.data.status || 'idle',
        progress: data.data.progress || 0,
        current_file: data.data.current_file || ''
      }
    }
  }

  ws.onclose = () => {
    wsConnected.value = false
    // Reconnect after 5 seconds
    setTimeout(connectWebSocket, 5000)
  }

  ws.onerror = () => {
    ws.close()
  }
}

const handleReindex = async () => {
  if (!confirm('This will rebuild the entire index. Continue?')) return

  reindexing.value = true
  try {
    await reindexDocuments()
    alert('Reindexing completed!')
    await loadDashboardData()
  } catch (err) {
    alert('Reindexing failed: ' + err.message)
  } finally {
    reindexing.value = false
  }
}

const handleSaveConfig = async () => {
  savingConfig.value = true
  try {
    await updateRagConfig({
      chunk_size: config.value.chunk_size,
      chunk_overlap: config.value.chunk_overlap,
      top_k: config.value.top_k,
      temperature: config.value.temperature,
      llm_model: config.value.llm_model,
    })
    alert('Configuration saved!')
  } catch (err) {
    alert('Failed to save config: ' + err.message)
  } finally {
    savingConfig.value = false
  }
}

onMounted(() => {
  loadDashboardData()
  connectWebSocket()
  // Refresh data every 10 seconds
  const interval = setInterval(loadDashboardData, 10000)
  onUnmounted(() => {
    clearInterval(interval)
    if (ws) ws.close()
  })
})
</script>

<template>
  <div class="dashboard-panel">
    <DashboardHeader :ws-connected="wsConnected" @close="emit('close')" />

    <div v-if="loading" class="dashboard-loading">
      <div class="loading-spinner"></div>
      <span>Loading dashboard...</span>
    </div>

    <div v-else class="dashboard-content">
      <IndexingProgress :indexing-status="indexingStatus" />

      <DashboardStats :stats="stats" :metrics="metrics" />

      <DashboardCharts 
        :chunks-distribution="chunksDistribution"
        :similarity-distribution="similarityDistribution"
        :documents-timeline="documentsTimeline"
      />

      <DashboardConfig 
        :config="config"
        :saving-config="savingConfig"
        :reindexing="reindexing"
        @save-config="handleSaveConfig"
        @reindex="handleReindex"
      />
    </div>
  </div>
</template>

<style scoped>
.dashboard-panel {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: min(1200px, 95vw);
  height: min(800px, 90vh);
  background: rgba(15, 23, 42, 0.98);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: 20px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6);
  z-index: 5000;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.dashboard-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;
  gap: 16px;
  color: var(--text-muted);
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(99, 102, 241, 0.2);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.dashboard-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

@media (max-width: 900px) {
  .dashboard-panel {
    width: 100vw;
    height: 100vh;
    border-radius: 0;
  }
}
</style>