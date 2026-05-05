<script setup>
import { computed } from 'vue'
import { Line, Bar } from 'vue-chartjs'

const props = defineProps({
  chunksDistribution: Object,
  similarityDistribution: Object,
  documentsTimeline: Object
})

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
  labels: props.chunksDistribution.labels,
  datasets: [{
    label: 'Chunks',
    backgroundColor: 'rgba(99, 102, 241, 0.5)',
    borderColor: 'rgba(99, 102, 241, 1)',
    borderWidth: 1,
    data: props.chunksDistribution.data
  }]
}))

const similarityChartData = computed(() => ({
  labels: props.similarityDistribution.labels,
  datasets: [{
    label: 'Similarity Score',
    backgroundColor: 'rgba(168, 85, 247, 0.5)',
    borderColor: 'rgba(168, 85, 247, 1)',
    borderWidth: 1,
    fill: true,
    data: props.similarityDistribution.data
  }]
}))

const timelineChartData = computed(() => ({
  labels: props.documentsTimeline.labels,
  datasets: [{
    label: 'Documents',
    backgroundColor: 'rgba(34, 197, 94, 0.5)',
    borderColor: 'rgba(34, 197, 94, 1)',
    borderWidth: 1,
    fill: true,
    data: props.documentsTimeline.data
  }]
}))
</script>

<template>
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
</template>

<style scoped>
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

@media (max-width: 900px) {
  .charts-grid {
    grid-template-columns: 1fr;
  }
}
</style>