<script setup>
defineProps({
  stages: {
    type: Array,
    default: () => [],
  },
  activeStageId: {
    type: String,
    default: '',
  },
})

defineEmits(['select-stage'])
</script>

<template>
  <aside class="rag-flow-timeline" aria-label="RAG flow timeline">
    <div class="timeline-header">
      <span class="eyebrow">Flow</span>
      <h2>RAG Pipeline</h2>
    </div>

    <button
      v-for="(stage, index) in stages"
      :key="stage.id"
      type="button"
      class="timeline-item"
      :class="[stage.status, { active: stage.id === activeStageId }]"
      @click="$emit('select-stage', index)"
    >
      <span class="stage-index">{{ index + 1 }}</span>
      <span class="stage-copy">
        <span class="stage-title">{{ stage.title }}</span>
        <span class="stage-status">{{ stage.status }}</span>
      </span>
      <span class="stage-time">{{ stage.duration_ms }}ms</span>
    </button>
  </aside>
</template>

<style scoped>
.rag-flow-timeline {
  min-width: 240px;
  padding: 18px;
  background: var(--surface-container-low);
  border-right: 1px solid rgba(69, 70, 83, 0.2);
  overflow-y: auto;
}

.timeline-header {
  margin-bottom: 16px;
}

.eyebrow {
  display: block;
  margin-bottom: 4px;
  color: var(--primary);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

.timeline-header h2 {
  margin: 0;
  font-size: 18px;
  color: var(--on-surface);
}

.timeline-item {
  width: 100%;
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  padding: 10px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--on-surface-variant);
  text-align: left;
}

.timeline-item:hover,
.timeline-item.active {
  background: rgba(129, 140, 248, 0.12);
  color: var(--on-surface);
  border-color: rgba(129, 140, 248, 0.35);
}

.timeline-item.failed {
  border-color: rgba(248, 113, 113, 0.4);
}

.timeline-item.skipped {
  opacity: 0.78;
}

.stage-index {
  width: 26px;
  height: 26px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--surface-container);
  font-size: 12px;
  font-weight: 700;
}

.timeline-item.completed .stage-index {
  background: rgba(34, 197, 94, 0.16);
  color: #86efac;
}

.timeline-item.failed .stage-index {
  background: rgba(239, 68, 68, 0.16);
  color: #fca5a5;
}

.stage-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.stage-title {
  font-size: 13px;
  font-weight: 700;
  color: inherit;
}

.stage-status,
.stage-time {
  font-size: 11px;
  color: var(--on-surface-variant);
  text-transform: capitalize;
}
</style>
