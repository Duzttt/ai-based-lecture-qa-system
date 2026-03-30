<script setup>
import { ref } from 'vue'

const emit = defineEmits(['open-settings', 'open-admin', 'open-chunkviz'])

const activeNav = ref('library')

const navItems = [
  { id: 'library', label: 'Library', icon: 'M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V5h14v14zM7 7h2v2H7zm0 4h2v2H7zm0 4h2v2H7zm4-8h6v2h-6zm0 4h6v2h-6zm0 4h6v2h-6z' },
  { id: 'archive', label: 'Archive', icon: 'M20.54 5.23l-1.39-1.68C18.88 3.21 18.47 3 18 3H6c-.47 0-.88.21-1.16.55L3.46 5.23C3.17 5.57 3 6.02 3 6.5V19c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V6.5c0-.48-.17-.93-.46-1.27zM12 17.5L6.5 12H10v-2h4v2h3.5L12 17.5zM5.12 5l.81-1h12l.94 1H5.12z' },
  { id: 'studio', label: 'Studio', icon: 'M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.07.62-.07.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z' },
]
</script>

<template>
  <header class="topbar">
    <div class="topbar-left">
      <div class="brand">
        <div class="brand-icon">
          <span class="brand-icon-inner"></span>
        </div>
        <div class="brand-text">
          <span class="brand-title">The Academic Curator</span>
        </div>
      </div>
    </div>

    <nav class="topbar-nav">
      <button
        v-for="item in navItems"
        :key="item.id"
        class="nav-item"
        :class="{ active: activeNav === item.id }"
        @click="activeNav = item.id"
      >
        <svg class="nav-icon" viewBox="0 0 24 24" fill="currentColor">
          <path :d="item.icon" />
        </svg>
        <span class="nav-label">{{ item.label }}</span>
      </button>
    </nav>

    <div class="topbar-right">
      <button class="icon-btn" @click="emit('open-chunkviz')" title="Chunks">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M3 13h2v-2H3v2zm0 4h2v-2H3v2zm0-8h2V7H3v2zm4 4h14v-2H7v2zm0 4h14v-2H7v2zM7 7v2h14V7H7z"/></svg>
      </button>
      <button class="icon-btn" @click="emit('open-admin')" title="Admin">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z"/></svg>
      </button>
      <button class="icon-btn notification-btn" title="Notifications">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.89 2 2 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/></svg>
        <span class="notification-dot"></span>
      </button>
      <div class="avatar">
        <span class="avatar-letter">A</span>
      </div>
    </div>
  </header>
</template>

<style scoped>
.topbar {
  height: 56px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(19, 27, 46, 0.7);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(69, 70, 83, 0.15);
}

.topbar-left {
  display: flex;
  align-items: center;
  min-width: 200px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: linear-gradient(135deg, #bdc2ff 0%, #818cf8 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.brand-icon-inner {
  width: 14px;
  height: 14px;
  border-radius: 4px;
  background: rgba(11, 19, 38, 0.9);
}

.brand-title {
  font-family: var(--font-headline);
  font-size: 15px;
  font-weight: 700;
  color: var(--on-surface);
  letter-spacing: -0.01em;
}

.topbar-nav {
  display: flex;
  align-items: center;
  gap: 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: var(--on-surface-variant);
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.nav-item:hover {
  background: rgba(189, 194, 255, 0.06);
  color: var(--on-surface);
}

.nav-item.active {
  background: rgba(129, 140, 248, 0.12);
  color: var(--primary);
}

.nav-icon {
  width: 18px;
  height: 18px;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 200px;
  justify-content: flex-end;
}

.icon-btn {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: var(--on-surface-variant);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
}

.icon-btn svg {
  width: 18px;
  height: 18px;
}

.icon-btn:hover {
  background: rgba(189, 194, 255, 0.06);
  color: var(--on-surface);
}

.notification-btn {
  position: relative;
}

.notification-dot {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--tertiary);
  border: 1.5px solid var(--surface-container-low);
}

.avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: linear-gradient(135deg, #818cf8, #6366f1);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: 6px;
  cursor: pointer;
}

.avatar-letter {
  font-family: var(--font-headline);
  font-size: 13px;
  font-weight: 700;
  color: white;
}

@media (max-width: 900px) {
  .nav-label {
    display: none;
  }
  .brand-title {
    display: none;
  }
}
</style>
