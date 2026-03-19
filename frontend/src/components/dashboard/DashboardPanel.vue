<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { Line, Bar, Doughnut } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js'
import { getDashboardStats, getDashboardMetrics, getDashboardChunksDistribution, getDashboardSimilarityDistribution, getDashboardDocumentsTimeline, updateRagConfig, reindexDocuments } from '../../services/api'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

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

// Chart options
const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      labels: { color: '#9ca3af' }
    }
  },
  scales: {
    x: {
      ticks: { color: '#9ca3af' },
      grid: { color: 'rgba(255,255,255,0.05)' }
    },
    y: {
      ticks: { color: '#9ca3af' },
      grid: { color: 'rgba(255,255,255,0.05)' }
    }
  }
}))

const chunksChartData = computed(() => ({
  labels: chunksDistribution.value.labels,
  datasets: [{
    label: 'Chunks',
    backgroundColor: 'rgba(99, 102, 241, 0.5)',
    borderColor: 'rgba(99, 102, 241, 1)',
    borderWidth: 1,
    data: chunksDistribution.value.data
  }]
}))

const similarityChartData = computed(() => ({
  labels: similarityDistribution.value.labels,
  datasets: [{
    label: 'Similarity Score',
    backgroundColor: 'rgba(168, 85, 247, 0.5)',
    borderColor: 'rgba(168, 85, 247, 1)',
    borderWidth: 1,
    fill: true,
    data: similarityDistribution.value.data
  }]
}))

const timelineChartData = computed(() => ({
  labels: documentsTimeline.value.labels,
  datasets: [{
    label: 'Documents',
    backgroundColor: 'rgba(34, 197, 94, 0.5)',
    borderColor: 'rgba(34, 197, 94, 1)',
    borderWidth: 1,
    fill: true,
    data: documentsTimeline.value.data
  }]
}))

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

const formatSize = (kb) => {
  if (kb < 1024) return `${kb.toFixed(1)} KB`
  return `${(kb / 1024).toFixed(2)} MB`
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
    <div class="dashboard-header">
      <div class="dashboard-title">
        <span>📊</span>
        <span>RAG Index Status Dashboard</span>
      </div>
      <div class="dashboard-actions">
        <span class="ws-status" :class="{ connected: wsConnected }">
          {{ wsConnected ? '● Live' : '○ Disconnected' }}
        </span>
        <button class="close-btn" @click="emit('close')">✕</button>
      </div>
    </div>

    <div v-if="loading" class="dashboard-loading">
      <div class="loading-spinner"></div>
      <span>Loading dashboard...</span>
    </div>

    <div v-else class="dashboard-content">
      <!-- Indexing Progress -->
      <div v-if="indexingStatus.status === 'running' || indexingStatus.status === 'queued'" class="indexing-progress-card">
        <div class="progress-header">
          <span class="progress-title">
            <span class="pulse-icon"></span>
            Indexing in Progress
          </span>
          <span class="progress-status">{{ indexingStatus.status }}</span>
        </div>
        <div class="progress-bar-wrap">
          <div class="progress-bar" :style="{ width: (indexingStatus.progress * 100) + '%' }"></div>
        </div>
        <div class="progress-info">
          <span>{{ Math.round(indexingStatus.progress * 100) }}% complete</span>
          <span v-if="indexingStatus.current_file">{{ indexingStatus.current_file }}</span>
        </div>
      </div>

      <!-- Stats Cards -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-icon doc">📄</div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.documents.total }}</div>
            <div class="stat-label">Documents</div>
            <div class="stat-sub">{{ stats.documents.total_pages }} pages · {{ stats.documents.total_chunks }} chunks</div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon vector">📏</div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.vectors.total_vectors }}</div>
            <div class="stat-label">Vectors</div>
            <div class="stat-sub">{{ stats.vectors.index_type }} · {{ stats.vectors.dimension }}D</div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon perf">⚡</div>
          <div class="stat-content">
            <div class="stat-value">{{ metrics.retrieval_time_ms.toFixed(1) }}ms</div>
            <div class="stat-label">Retrieval Time</div>
            <div class="stat-sub">Embedding: {{ metrics.embedding_time_ms.toFixed(1) }}ms</div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon storage">💾</div>
          <div class="stat-content">
            <div class="stat-value">{{ formatSize(stats.storage.faiss_index_size_kb) }}</div>
            <div class="stat-label">Index Size</div>
            <div class="stat-sub">Docs: {{ formatSize(stats.storage.documents_size_kb) }}</div>
          </div>
        </div>
      </div>

      <!-- Charts -->
      <div class="charts-grid">
        <div class="chart-card">
          <div class="chart-title">📊 Chunk Length Distribution</div>
          <div class="chart-body">
            <Bar :data="chunksChartData" :options="chartOptions" />
          </div>
        </div>

        <div class="chart-card">
          <div class="chart-title">🎯 Similarity Score Distribution</div>
          <div class="chart-body">
            <Line :data="similarityChartData" :options="chartOptions" />
          </div>
        </div>

        <div class="chart-card full-width">
          <div class="chart-title">📅 Document Upload Timeline</div>
          <div class="chart-body">
            <Line :data="timelineChartData" :options="chartOptions" />
          </div>
        </div>
      </div>

      <!-- Configuration Panel -->
      <div class="config-panel">
        <div class="config-header">
          <span class="config-title">⚙️ RAG Configuration</span>
        </div>
        <div class="config-grid">
          <div class="config-item">
            <label>Chunk Size</label>
            <input v-model.number="config.chunk_size" type="number" min="100" max="2000" step="50" />
          </div>
          <div class="config-item">
            <label>Chunk Overlap</label>
            <input v-model.number="config.chunk_overlap" type="number" min="0" max="500" step="10" />
          </div>
          <div class="config-item">
            <label>Top K</label>
            <input v-model.number="config.top_k" type="number" min="1" max="20" step="1" />
          </div>
          <div class="config-item">
            <label>Temperature</label>
            <input v-model.number="config.temperature" type="number" min="0" max="2" step="0.1" />
          </div>
        </div>
        <div class="config-actions">
          <button class="btn btn-primary" @click="handleSaveConfig" :disabled="savingConfig">
            {{ savingConfig ? 'Saving...' : 'Save Configuration' }}
          </button>
          <button class="btn btn-danger" @click="handleReindex" :disabled="reindexing">
            {{ reindexing ? 'Reindexing...' : '🔄 Rebuild Index' }}
          </button>
        </div>
      </div>
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

.dashboard-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(99, 102, 241, 0.1);
}

.dashboard-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 600;
  color: white;
}

.dashboard-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ws-status {
  font-size: 11px;
  color: var(--text-muted);
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.ws-status.connected {
  color: #22c55e;
  background: rgba(34, 197, 94, 0.1);
  border-color: rgba(34, 197, 94, 0.3);
}

.close-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  transition: all 0.2s;
}

.close-btn:hover {
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.3);
  color: #ef4444;
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

.indexing-progress-card {
  margin-bottom: 20px;
  padding: 16px;
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: 12px;
}

.progress-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.progress-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: white;
}

.pulse-icon {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.2); }
}

.progress-status {
  font-size: 11px;
  color: var(--accent);
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.2);
  text-transform: uppercase;
}

.progress-bar-wrap {
  height: 8px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 8px;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), #a855f7);
  transition: width 0.3s ease;
  border-radius: 4px;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-muted);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  gap: 14px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  transition: all 0.2s;
}

.stat-card:hover {
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(99, 102, 241, 0.3);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  flex-shrink: 0;
}

.stat-icon.doc { background: rgba(34, 197, 94, 0.15); }
.stat-icon.vector { background: rgba(99, 102, 241, 0.15); }
.stat-icon.perf { background: rgba(251, 191, 36, 0.15); }
.stat-icon.storage { background: rgba(168, 85, 247, 0.15); }

.stat-content {
  flex: 1;
  min-width: 0;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: white;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.stat-sub {
  font-size: 10px;
  color: var(--text-muted);
  margin-top: 4px;
}

.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.chart-card {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  padding: 16px;
}

.chart-card.full-width {
  grid-column: 1 / -1;
}

.chart-title {
  font-size: 13px;
  font-weight: 600;
  color: white;
  margin-bottom: 12px;
}

.chart-body {
  height: 200px;
}

.config-panel {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  padding: 16px;
}

.config-header {
  margin-bottom: 16px;
}

.config-title {
  font-size: 14px;
  font-weight: 600;
  color: white;
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.config-item label {
  display: block;
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 6px;
  text-transform: uppercase;
}

.config-item input {
  width: 100%;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid rgba(55, 65, 81, 0.8);
  background: rgba(2, 6, 23, 0.8);
  color: var(--text-main);
  font-size: 13px;
  outline: none;
}

.config-item input:focus {
  border-color: var(--accent);
}

.config-actions {
  display: flex;
  gap: 12px;
}

.btn {
  padding: 10px 20px;
  border-radius: 8px;
  border: none;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary {
  background: linear-gradient(135deg, var(--accent), #a855f7);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 8px 20px -10px rgba(99, 102, 241, 0.5);
}

.btn-danger {
  background: rgba(239, 68, 68, 0.2);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #fca5a5;
}

.btn-danger:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.3);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Responsive */
@media (max-width: 900px) {
  .dashboard-panel {
    width: 100vw;
    height: 100vh;
    border-radius: 0;
  }

  .charts-grid {
    grid-template-columns: 1fr;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }

  .config-grid {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
