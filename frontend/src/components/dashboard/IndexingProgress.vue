<script setup>
const props = defineProps({
  indexingStatus: Object
})
</script>

<template>
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
</template>

<style scoped>
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
</style>