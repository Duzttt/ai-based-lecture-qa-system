<script setup>
const emit = defineEmits(['open-settings', 'open-admin'])
</script>

<template>
  <header class="topbar">
    <div class="topbar-left">
      <div class="logo-dot">
        <span></span>
      </div>
      <div class="topbar-title">
        <span class="topbar-title-main">Lecture Note Q&A</span>
        <span class="topbar-title-sub">RAG Powered</span>
      </div>
    </div>
    <div class="topbar-center">
      <button class="pill-btn admin-btn" @click="emit('open-admin')">
        <span class="icon">🛠️</span>
        Admin
      </button>
      <button class="pill-btn" @click="emit('open-settings')">
        <span class="icon">⚙️</span>
        Settings
      </button>
    </div>
    <div class="topbar-right">
      <button class="icon-btn">🔔</button>
      <div class="avatar"></div>
    </div>
  </header>
</template>

<style scoped>
.topbar {
  height: 56px;
  padding: 0 16px 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(55, 65, 81, 0.8);
  background: linear-gradient(135deg, #020617, #111827);
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo-dot {
  width: 26px;
  height: 26px;
  border-radius: 10px;
  background: radial-gradient(circle at 30% 20%, #a855f7, #6366f1);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 0 1px rgba(129, 140, 248, 0.35);
}

.logo-dot span {
  width: 12px;
  height: 12px;
  border-radius: 4px;
  background: rgba(15, 23, 42, 0.95);
}

.topbar-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.topbar-title-main {
  font-size: 14px;
  font-weight: 600;
}

.topbar-title-sub {
  font-size: 11px;
  color: var(--text-muted);
}

.topbar-center {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  flex-wrap: nowrap;
  padding: 0 12px;
}

.pill-btn {
  padding: 6px 14px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-top-color: rgba(255, 255, 255, 0.15);
  border-left-color: rgba(255, 255, 255, 0.15);
  font-size: 12px;
  background: linear-gradient(
    145deg,
    rgba(15, 25, 40, 0.6) 0%,
    rgba(25, 35, 55, 0.7) 100%
  );
  color: var(--text-main);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  box-shadow:
    0 5px 15px -5px rgba(0, 0, 0, 0.5),
    inset 0 1px 1px rgba(255, 255, 255, 0.1);
  transition: all 0.2s;
}

.pill-btn:hover {
  border-color: rgba(255, 255, 255, 0.2);
}

.pill-btn span.icon {
  font-size: 13px;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.icon-btn {
  width: 26px;
  height: 26px;
  border-radius: 999px;
  border: 1px solid rgba(55, 65, 81, 0.9);
  background: rgba(15, 23, 42, 0.95);
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.icon-btn:hover {
  color: var(--text-main);
  border-color: rgba(255, 255, 255, 0.2);
}

.avatar {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  border: 2px solid #4ade80;
  background: linear-gradient(135deg, #06b6d4, #a855f7);
  cursor: pointer;
}
</style>
