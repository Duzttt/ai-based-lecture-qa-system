<script setup>
const props = defineProps({
  indexingStatus: Object
})

const emit = defineEmits(['close'])
</script>

<template>
  <div class="admin-header">
    <div class="admin-title">
      <span class="title-icon">🛠️</span>
      <span>Admin Dashboard</span>
    </div>
    <div class="admin-actions">
      <span class="status-badge" :class="indexingStatus.status">
        {{ indexingStatus.status === 'running' ? '⏳ Indexing...' : '✓ Ready' }}
      </span>
      <button class="close-btn" @click="emit('close')" aria-label="Close admin menu">✕</button>
    </div>
  </div>
</template>

<style scoped>
.admin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(99, 102, 241, 0.1);
}

.admin-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 600;
  color: white;
}

.title-icon {
  font-size: 18px;
}

.admin-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-badge {
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(34, 197, 94, 0.1);
  color: #22c55e;
  border: 1px solid rgba(34, 197, 94, 0.3);
}

.status-badge.running {
  background: rgba(251, 191, 36, 0.1);
  color: #fbbf24;
  border-color: rgba(251, 191, 36, 0.3);
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
}

.close-btn:hover {
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.3);
  color: #ef4444;
}
</style>