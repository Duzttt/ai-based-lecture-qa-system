<script setup>
import Topbar from './components/layout/Topbar.vue'
import SourcesPanel from './components/layout/SourcesPanel.vue'
import ChatPanel from './components/chat/ChatPanel.vue'
import StudioPanel from './components/layout/StudioPanel.vue'
import ComparisonView from './components/documents/ComparisonView.vue'
import SettingsModal from './components/settings/SettingsModal.vue'
import AdminDashboard from './components/admin/AdminDashboard.vue'
import ChunkViz from './components/shared/ChunkViz.vue'
import { ref, computed, onMounted } from 'vue'
import { useLlmSettingsStore } from './stores/llmSettingsStore'

const llmStore = useLlmSettingsStore()

onMounted(() => {
  llmStore.loadProviders()
})

const showSettings = ref(false)
const showAdmin = ref(false)
const showChunkViz = ref(false)
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
    <Topbar
      @open-settings="showSettings = true"
      @open-admin="showAdmin = true"
      @open-chunkviz="showChunkViz = true"
    />
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
    <ChunkViz :show="showChunkViz" @close="showChunkViz = false" />
  </div>
</template>

<style scoped>
.app-shell {
  width: 100%;
  height: 100%;
  background: var(--surface);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.main {
  flex: 1;
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr) 280px;
  grid-template-rows: minmax(0, 1fr);
  gap: 1px;
  background: rgba(69, 70, 83, 0.08);
  min-height: 0;
}

@media (max-width: 1024px) {
  .app-shell {
    width: 100vw;
    height: 100vh;
  }
}

@media (max-width: 900px) {
  .main {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
