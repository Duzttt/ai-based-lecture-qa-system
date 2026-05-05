<script setup>
const props = defineProps({
  stats: Object,
  queryStats: Object
})

const formatSize = (kb) => {
  if (kb < 1024) return `${kb.toFixed(1)} KB`
  return `${(kb / 1024).toFixed(2)} MB`
}

const getHealthColor = (status) => {
  switch (status) {
    case 'healthy': return '#22c55e'
    case 'warning': return '#fbbf24'
    case 'empty': return '#f97316'
    default: return '#6b7280'
  }
}
</script>

<template>
  <div class="tab-content">
    <!-- Stats Grid -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon docs">📄</div>
        <div class="stat-body">
          <div class="stat-value">{{ stats.documents.total }}</div>
          <div class="stat-label">Documents</div>
          <div class="stat-sub">{{ stats.documents.chunks }} chunks · {{ stats.documents.pages }} pages</div>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon vectors">📏</div>
        <div class="stat-body">
          <div class="stat-value">{{ stats.vectors.count.toLocaleString() }}</div>
          <div class="stat-label">Vectors</div>
          <div class="stat-sub">{{ stats.vectors.index_type }} · {{ stats.vectors.dimension }}D</div>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon queries">⚡</div>
        <div class="stat-body">
          <div class="stat-value">{{ stats.queries.today }}</div>
          <div class="stat-label">Today's Queries</div>
          <div class="stat-sub">{{ stats.queries.week }} this week</div>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon latency">⏱️</div>
        <div class="stat-body">
          <div class="stat-value">{{ stats.queries.avg_latency_ms }}ms</div>
          <div class="stat-label">Avg Latency</div>
          <div class="stat-sub">P95: {{ stats.queries.p95_latency_ms }}ms</div>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon cache">💾</div>
        <div class="stat-body">
          <div class="stat-value">{{ stats.queries.cache_hit_rate }}%</div>
          <div class="stat-label">Cache Hit Rate</div>
          <div class="stat-sub">7-day average</div>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon storage">💽</div>
        <div class="stat-body">
          <div class="stat-value">{{ formatSize(stats.storage.faiss_size_kb) }}</div>
          <div class="stat-label">Index Size</div>
          <div class="stat-sub">Docs: {{ formatSize(stats.storage.docs_size_kb) }}</div>
        </div>
      </div>
    </div>

    <!-- Health Status -->
    <div class="health-section">
      <h3 class="section-title">System Health</h3>
      <div class="health-grid">
        <div class="health-item">
          <span class="health-label">FAISS Index</span>
          <span class="health-status" :style="{ color: getHealthColor(stats.health.faiss_index) }">
            {{ stats.health.faiss_index }}
          </span>
        </div>
        <div class="health-item">
          <span class="health-label">LLM Service</span>
          <span class="health-status" :style="{ color: getHealthColor(stats.health.llm_service) }">
            {{ stats.health.llm_service }}
          </span>
        </div>
        <div class="health-item">
          <span class="health-label">Disk Space</span>
          <span class="health-status" :style="{ color: getHealthColor(stats.health.disk_space) }">
            {{ stats.health.disk_space }}
          </span>
        </div>
        <div class="health-item">
          <span class="health-label">Memory</span>
          <span class="health-status" :style="{ color: getHealthColor(stats.health.memory) }">
            {{ stats.health.memory }}
          </span>
        </div>
      </div>
    </div>

    <!-- Query Distribution -->
    <div class="query-section">
      <h3 class="section-title">Query Statistics (24h)</h3>
      <div class="query-stats">
        <div class="query-stat">
          <span class="query-value">{{ queryStats.total_queries }}</span>
          <span class="query-label">Total Queries</span>
        </div>
        <div class="query-stat">
          <span class="query-value">{{ queryStats.avg_latency_ms }}ms</span>
          <span class="query-label">Avg Latency</span>
        </div>
      </div>
      <div v-if="queryStats.type_distribution?.length" class="type-dist">
        <div v-for="item in queryStats.type_distribution" :key="item.query_type" class="type-item">
          <span class="type-name">{{ item.query_type }}</span>
          <span class="type-count">{{ item.count }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tab-content {
  padding: 20px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  display: flex;
  gap: 12px;
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
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.stat-icon.docs { background: rgba(34, 197, 94, 0.15); }
.stat-icon.vectors { background: rgba(99, 102, 241, 0.15); }
.stat-icon.queries { background: rgba(251, 191, 36, 0.15); }
.stat-icon.latency { background: rgba(168, 85, 247, 0.15); }
.stat-icon.cache { background: rgba(236, 72, 153, 0.15); }
.stat-icon.storage { background: rgba(20, 184, 166, 0.15); }

.stat-body {
  flex: 1;
  min-width: 0;
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: white;
  margin-bottom: 2px;
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
  margin-top: 2px;
}

.health-section, .query-section {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: white;
  margin-bottom: 12px;
}

.health-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}

.health-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
}

.health-label {
  font-size: 12px;
  color: var(--text-muted);
}

.health-status {
  font-size: 12px;
  font-weight: 600;
  text-transform: capitalize;
}

.query-stats {
  display: flex;
  gap: 24px;
  margin-bottom: 16px;
}

.query-stat {
  display: flex;
  flex-direction: column;
}

.query-value {
  font-size: 20px;
  font-weight: 700;
  color: white;
}

.query-label {
  font-size: 11px;
  color: var(--text-muted);
}

.type-dist {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.type-item {
  display: flex;
  gap: 8px;
  padding: 6px 12px;
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 8px;
  font-size: 12px;
}

.type-name {
  color: var(--text-main);
}

.type-count {
  color: var(--accent);
  font-weight: 600;
}
</style>