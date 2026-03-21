<script setup>
import Topbar from './components/layout/Topbar.vue'
import SourcesPanel from './components/layout/SourcesPanel.vue'
import ChatPanel from './components/chat/ChatPanel.vue'
import StudioPanel from './components/layout/StudioPanel.vue'
import ComparisonView from './components/documents/ComparisonView.vue'
import SettingsModal from './components/settings/SettingsModal.vue'
import AdminDashboard from './components/admin/AdminDashboard.vue'
import { ref, computed } from 'vue'

const showSettings = ref(false)
const showAdmin = ref(false)
const compareMode = ref(false)
const selectedDocs = ref([])

const showComparison = computed(() => {
  return compareMode.value && selectedDocs.value.length >= 2
})

const handleSelectionChange = (docs) => {
  selectedDocs.value = docs
}

const handleToggleCompare = (isActive) => {
  compareMode.value = isActive
  if (!isActive) {
    selectedDocs.value = []
  }
}

const handleCloseComparison = () => {
  compareMode.value = false
  selectedDocs.value = []
}
</script>

<template>
  <div class="app-shell">
    <Topbar @open-settings="showSettings = true" @open-admin="showAdmin = true" />
    <main class="main">
      <SourcesPanel 
        @selection-change="handleSelectionChange"
        @toggle-compare="handleToggleCompare"
      />
      <ChatPanel 
        v-if="!showComparison" 
        :selected-sources="selectedDocs" 
      />
      <ComparisonView 
        v-else 
        :selected-docs="selectedDocs"
        @close="handleCloseComparison"
      />
      <StudioPanel />
    </main>
    <SettingsModal v-model:show="showSettings" />
    <AdminDashboard v-if="showAdmin" @close="showAdmin = false" />
  </div>
</template>

<style scoped>
.app-shell {
  width: min(1280px, 100vw);
  height: min(720px, 100vh - 40px);
  background: rgba(15, 23, 42, 0.95);
  border-radius: 20px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  backdrop-filter: blur(16px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 24px 80px rgba(15, 23, 42, 0.8);
}

.main {
  flex: 1;
  display: grid;
  grid-template-columns: 260px minmax(0, 1.4fr) 270px;
  grid-template-rows: minmax(0, 1fr);
  gap: var(--spacing-unit);
  padding: calc(var(--spacing-unit) + 2px) var(--spacing-unit)
    calc(var(--spacing-unit) * 1.75);
  background: radial-gradient(circle at top, #020617 0, #020617 45%, #000 90%);
  min-width: 0;
  min-height: 0;
}

@media (max-width: 1024px) {
  .app-shell {
    width: 100vw;
    height: 100vh;
    border-radius: 0;
  }
}

@media (max-width: 900px) {
  .main {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
