<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { getRagDemoTrace } from '../../services/api'
import RagEvidencePanel from './RagEvidencePanel.vue'
import RagFlowTimeline from './RagFlowTimeline.vue'
import RagStageDetail from './RagStageDetail.vue'

defineEmits(['close'])

const query = ref('What is retrieval augmented generation?')
const trace = ref(null)
const activeIndex = ref(0)
const isLoading = ref(false)
const isPlaying = ref(false)
const technicalView = ref(false)
const error = ref('')
const timers = []

const stages = computed(() => trace.value?.stages || [])
const activeStage = computed(() => stages.value[activeIndex.value] || null)
const activeStageId = computed(() => activeStage.value?.id || '')

const clearTimers = () => {
  while (timers.length) {
    clearTimeout(timers.pop())
  }
}

const stageDelay = (stage) => {
  const realDuration = Number(stage?.duration_ms || 0)
  return Math.min(Math.max(realDuration, 900), 1800)
}

const playTrace = () => {
  clearTimers()
  if (!stages.value.length) return
  activeIndex.value = 0
  isPlaying.value = true

  const scheduleNext = (index) => {
    if (index >= stages.value.length - 1) {
      isPlaying.value = false
      return
    }
    const timer = setTimeout(() => {
      activeIndex.value = index + 1
      scheduleNext(index + 1)
    }, stageDelay(stages.value[index]))
    timers.push(timer)
  }

  scheduleNext(0)
}

const runDemo = async () => {
  const trimmedQuery = query.value.trim()
  if (!trimmedQuery) {
    error.value = 'Enter a question to run the demo.'
    return
  }

  clearTimers()
  isLoading.value = true
  isPlaying.value = false
  error.value = ''

  try {
    trace.value = await getRagDemoTrace({
      query: trimmedQuery,
      top_k: 5,
      include_answer: true,
    })
    playTrace()
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || 'Failed to run RAG demo.'
  } finally {
    isLoading.value = false
  }
}

const replay = () => {
  if (trace.value) {
    playTrace()
  }
}

const selectStage = (index) => {
  clearTimers()
  isPlaying.value = false
  activeIndex.value = index
}

onBeforeUnmount(() => {
  clearTimers()
})
</script>

<template>
  <section class="rag-demo-view">
    <header class="demo-header">
      <div>
        <span class="eyebrow">Live Demo</span>
        <h1>RAG Trace Visualization</h1>
        <p>Show how a lecture-note question moves through retrieval, context building, and answer generation.</p>
      </div>
      <button type="button" class="secondary-btn" @click="$emit('close')">Back to Workspace</button>
    </header>

    <div class="demo-controls">
      <label class="query-field">
        <span>Question</span>
        <input v-model="query" type="text" :disabled="isLoading" @keyup.enter="runDemo">
      </label>
      <button type="button" class="primary-btn" :disabled="isLoading" @click="runDemo">
        {{ isLoading ? 'Running' : 'Run Demo' }}
      </button>
      <button type="button" class="secondary-btn" :disabled="!trace || isLoading" @click="replay">
        {{ isPlaying ? 'Playing' : 'Replay' }}
      </button>
      <label class="toggle-field">
        <input v-model="technicalView" type="checkbox">
        <span>Technical view</span>
      </label>
    </div>

    <div v-if="error" class="demo-error" role="alert">{{ error }}</div>

    <div class="demo-body">
      <RagFlowTimeline
        :stages="stages"
        :active-stage-id="activeStageId"
        @select-stage="selectStage"
      />
      <RagStageDetail
        :stage="activeStage"
        :technical-view="technicalView"
      />
      <RagEvidencePanel
        :chunks="trace?.retrieved_chunks || []"
        :context-preview="trace?.context_preview || ''"
        :answer="trace?.answer || ''"
        :technical-view="technicalView"
      />
    </div>
  </section>
</template>

<style scoped>
.rag-demo-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--surface);
}

.demo-header,
.demo-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 22px;
  border-bottom: 1px solid rgba(69, 70, 83, 0.18);
  background: var(--surface-container-low);
}

.demo-header h1,
.demo-header p {
  margin: 0;
}

.demo-header h1 {
  margin-bottom: 4px;
  font-size: 24px;
  color: var(--on-surface);
}

.demo-header p {
  color: var(--on-surface-variant);
  font-size: 13px;
}

.eyebrow {
  display: block;
  margin-bottom: 4px;
  color: var(--primary);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

.demo-controls {
  justify-content: flex-start;
  flex-wrap: wrap;
  background: var(--surface-container-lowest);
}

.query-field {
  flex: 1;
  min-width: 280px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--on-surface-variant);
  font-size: 12px;
  font-weight: 700;
}

.query-field input {
  width: 100%;
  height: 40px;
  border-radius: 8px;
  border: 1px solid rgba(69, 70, 83, 0.4);
  background: var(--surface-container);
  color: var(--on-surface);
  padding: 0 12px;
  font-size: 14px;
}

.primary-btn,
.secondary-btn {
  height: 40px;
  padding: 0 14px;
  border-radius: 8px;
  border: 1px solid transparent;
  font-weight: 700;
}

.primary-btn {
  background: var(--primary-container);
  color: var(--on-primary);
}

.secondary-btn {
  background: var(--surface-container);
  color: var(--on-surface);
  border-color: rgba(69, 70, 83, 0.4);
}

.primary-btn:disabled,
.secondary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.toggle-field {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--on-surface-variant);
  font-size: 13px;
  font-weight: 700;
}

.demo-error {
  margin: 12px 22px 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.12);
  color: #fca5a5;
  border: 1px solid rgba(239, 68, 68, 0.28);
  font-size: 13px;
}

.demo-body {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr) 340px;
}

@media (max-width: 1100px) {
  .demo-body {
    grid-template-columns: 1fr;
  }
}
</style>
