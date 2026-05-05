<script setup>
const props = defineProps({
  wsConnected: Boolean
})

const emit = defineEmits(['close'])
</script>

<template>
  <div class="dashboard-header">
    <div class="dashboard-title">
      <span>📊</span>
      <span>RAG Index Status Dashboard</span>
    </div>
    <div class="dashboard-actions">
      <span class="ws-status" :class="{ connected: wsConnected }">
        {{ wsConnected ? '● Live' : '○ Disconnected' }}
      </span>
      <button class="close-btn" @click="emit('close')" aria-label="Close header">✕</button>
    </div>
  </div>
</template>

<style scoped>
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
</style>