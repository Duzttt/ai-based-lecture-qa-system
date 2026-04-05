<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { getQuestionSuggestions, recordSuggestionClick } from '../../services/api'

const props = defineProps({
  selectedDocuments: {
    type: Array,
    default: () => [],
  },
  disabled: {
    type: Boolean,
    default: false,
  },
  centered: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['question-select'])

const suggestions = ref([])
const isLoading = ref(false)
const error = ref('')
const collapsed = ref(false)
const generationTime = ref(null)

// Local cache for suggestions (keyed by sorted doc names)
const suggestionsCache = ref(new Map())
const CACHE_TTL = 5 * 60 * 1000 // 5 minutes

// Abort controller for cancelling in-flight requests
let abortController = null

let debounceTimer = null

const hasSuggestions = computed(() => suggestions.value.length > 0)
const hasSelection = computed(() => props.selectedDocuments.length > 0)
const canGenerate = computed(() => hasSelection.value && !isLoading.value && !props.disabled)
const visible = computed(() => !collapsed.value && (hasSuggestions.value || isLoading.value))

// Stable string key derived from selected doc IDs — changes only when
// the actual set of selected documents changes, not on every deep mutation.
const docIdKey = computed(() => {
  return props.selectedDocuments
    .map(doc => doc.name || doc.filename)
    .sort()
    .join(',')
})

watch(docIdKey, (newKey, oldKey) => {
  if (!newKey) {
    suggestions.value = []
    error.value = ''
    collapsed.value = false
    generationTime.value = null
    return
  }
  if (newKey !== oldKey) {
    collapsed.value = false
    debouncedGenerate()
  }
})

function debouncedGenerate() {
  if (debounceTimer) clearTimeout(debounceTimer)
  // Cancel any in-flight request
  if (abortController) {
    abortController.abort()
    abortController = null
  }
  debounceTimer = setTimeout(() => generateSuggestions(), 500)
}

function getCachedSuggestions(key) {
  const cached = suggestionsCache.value.get(key)
  if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
    return cached.data
  }
  if (cached) {
    suggestionsCache.value.delete(key)
  }
  return null
}

function setCachedSuggestions(key, data) {
  // Keep cache size reasonable
  if (suggestionsCache.value.size > 20) {
    const oldestKey = suggestionsCache.value.keys().next().value
    suggestionsCache.value.delete(oldestKey)
  }
  suggestionsCache.value.set(key, { data, timestamp: Date.now() })
}

const generateSuggestions = async () => {
  if (!canGenerate.value) return

  // Check local cache first
  const cacheKey = docIdKey.value
  const cached = getCachedSuggestions(cacheKey)
  if (cached) {
    suggestions.value = cached.suggestions
    generationTime.value = cached.generationTime
    return
  }

  // Cancel previous request if still pending
  if (abortController) {
    abortController.abort()
  }
  abortController = new AbortController()

  isLoading.value = true
  error.value = ''
  generationTime.value = null

  try {
    const docIds = props.selectedDocuments.map(doc => doc.name || doc.filename)
    const response = await getQuestionSuggestions(docIds)

    if (response.success && response.suggestions && response.suggestions.length > 0) {
      const mappedSuggestions = response.suggestions.map((text, index) => ({
        id: `s_${Date.now()}_${index}`,
        text,
        position: index,
      }))

      suggestions.value = mappedSuggestions
      generationTime.value = response.generation_time_ms

      // Cache the result
      setCachedSuggestions(cacheKey, {
        suggestions: mappedSuggestions,
        generationTime: response.generation_time_ms,
      })
    } else {
      error.value = response.message || 'No suggestions available'
      generateFallbackSuggestions()
    }
  } catch (err) {
    // Don't show error if request was aborted
    if (err.name === 'AbortError') return

    console.error('Failed to generate suggestions:', err)
    error.value = err.response?.data?.detail || err.message || 'Failed to generate suggestions'
    generateFallbackSuggestions()
  } finally {
    isLoading.value = false
    abortController = null
  }
}

const generateFallbackSuggestions = () => {
  const docNames = props.selectedDocuments.map(doc => doc.name || doc.filename)
  if (docNames.length === 0) return

  const docName = docNames[0].replace('.pdf', '')
  suggestions.value = [
    { id: `fb_${Date.now()}_0`, text: `What is the main topic covered in ${docName}?`, position: 0 },
    { id: `fb_${Date.now()}_1`, text: `Explain the key concepts from ${docName}.`, position: 1 },
    { id: `fb_${Date.now()}_2`, text: `What are the most important points in ${docName}?`, position: 2 },
  ]
}

const handleChipClick = async (suggestion) => {
  emit('question-select', suggestion.text)
  collapsed.value = true

  try {
    const docIds = props.selectedDocuments.map(doc => doc.name || doc.filename)
    await recordSuggestionClick(suggestion.text, docIds, suggestion.position)
  } catch (_) {
    // analytics — don't surface errors
  }
}

const handleRefresh = async () => {
  if (!canGenerate.value) return
  // Clear cache for current key to force regeneration
  suggestionsCache.value.delete(docIdKey.value)
  collapsed.value = false
  await generateSuggestions()
}

defineExpose({ generateSuggestions, refresh: handleRefresh })

onMounted(() => {
  if (hasSelection.value) generateSuggestions()
})

onUnmounted(() => {
  if (debounceTimer) clearTimeout(debounceTimer)
  if (abortController) abortController.abort()
})
</script>

<template>
  <Transition name="suggestions-fade">
    <div
      v-if="hasSelection && (visible || error)"
      class="question-suggestions"
      :class="{ 'is-disabled': disabled, 'is-centered': centered }"
    >
      <div class="suggestions-row">
        <!-- Label chip -->
        <span class="label-chip">
          <svg class="label-icon" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M8 2a1 1 0 0 1 .894.553l1.276 2.557 2.829.416a1 1 0 0 1 .554 1.705l-2.047 1.993.483 2.818a1 1 0 0 1-1.45 1.054L8 11.846l-2.539 1.25a1 1 0 0 1-1.45-1.054l.483-2.818L2.447 7.23a1 1 0 0 1 .554-1.705l2.829-.416L7.106 2.553A1 1 0 0 1 8 2z" fill="currentColor"/>
          </svg>
          Suggested
        </span>

        <!-- Skeleton loading -->
        <template v-if="isLoading">
          <span v-for="i in 3" :key="'skel_' + i" class="skeleton-chip" />
        </template>

        <!-- Suggestion chips -->
        <TransitionGroup v-else name="chip" tag="div" class="chips-wrap">
        <button
          v-for="suggestion in suggestions"
          :key="suggestion.id"
          type="button"
          class="suggestion-chip"
          @click="handleChipClick(suggestion)"
          :disabled="disabled"
        >
            <span class="chip-text">{{ suggestion.text }}</span>
            <svg class="chip-arrow" viewBox="0 0 12 12" fill="none" aria-hidden="true">
              <path d="M2 6h8M7 3l3 3-3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </TransitionGroup>

        <!-- Error inline -->
        <span v-if="error && !hasSuggestions && !isLoading" class="error-chip">
          {{ error }}
        </span>

        <!-- Refresh button -->
        <button
          v-if="hasSuggestions || isLoading"
          type="button"
          class="refresh-btn"
          aria-label="Refresh suggestions"
          @click="handleRefresh"
          :disabled="isLoading || !hasSelection"
        >
          <svg
            class="refresh-icon"
            :class="{ spinning: isLoading }"
            viewBox="0 0 16 16"
            fill="none"
            aria-hidden="true"
          >
            <path d="M13.65 2.35A7.958 7.958 0 0 0 8 0a8 8 0 1 0 7.745 6h-2.09A5.98 5.98 0 0 1 8 14 6 6 0 1 1 8 2c1.66 0 3.14.69 4.22 1.78L9 7h7V0l-2.35 2.35z" fill="currentColor"/>
          </svg>
        </button>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.question-suggestions {
  padding: 8px 0 4px;
  transition: opacity 0.3s ease;
}

.question-suggestions.is-disabled {
  opacity: 0.5;
  pointer-events: none;
}

.question-suggestions.is-centered .suggestions-row {
  justify-content: center;
}

/* --- Layout --- */
.suggestions-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.chips-wrap {
  display: contents;
}

/* --- Label chip --- */
.label-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  padding: 5px 10px;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.15);
  white-space: nowrap;
  flex-shrink: 0;
  user-select: none;
}

.label-icon {
  width: 12px;
  height: 12px;
  color: var(--accent, #6366f1);
}

/* --- Skeleton chips --- */
.skeleton-chip {
  display: inline-block;
  height: 32px;
  border-radius: 999px;
  background: linear-gradient(
    90deg,
    rgba(255, 255, 255, 0.04) 25%,
    rgba(255, 255, 255, 0.08) 50%,
    rgba(255, 255, 255, 0.04) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite ease-in-out;
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.skeleton-chip:nth-child(2) { width: 180px; }
.skeleton-chip:nth-child(3) { width: 150px; }
.skeleton-chip:nth-child(4) { width: 200px; }

@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* --- Suggestion chip --- */
.suggestion-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-main, #e2e8f0);
  font-size: 12px;
  line-height: 1.4;
  cursor: pointer;
  transition: background-color 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
  white-space: nowrap;
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.suggestion-chip:focus-visible {
  outline: 2px solid var(--accent, #6366f1);
  outline-offset: 2px;
}

.suggestion-chip:hover {
  background: rgba(99, 102, 241, 0.15);
  border-color: rgba(99, 102, 241, 0.4);
  box-shadow: 0 2px 12px rgba(99, 102, 241, 0.15);
  transform: translateY(-1px);
}

.suggestion-chip:active {
  transform: translateY(0);
}

.chip-text {
  overflow: hidden;
  text-overflow: ellipsis;
}

.chip-arrow {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
  color: var(--accent, #6366f1);
  opacity: 0;
  transform: translateX(-4px);
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.suggestion-chip:hover .chip-arrow {
  opacity: 1;
  transform: translateX(0);
}

/* --- Error chip --- */
.error-chip {
  display: inline-flex;
  align-items: center;
  padding: 5px 12px;
  border-radius: 999px;
  font-size: 11px;
  color: #fca5a5;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.15);
}

/* --- Refresh button --- */
.refresh-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-muted);
  cursor: pointer;
  transition: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease;
  flex-shrink: 0;
}

.refresh-btn:focus-visible {
  outline: 2px solid var(--accent, #6366f1);
  outline-offset: 2px;
}

.refresh-btn:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.15);
  border-color: rgba(99, 102, 241, 0.4);
  color: var(--accent, #6366f1);
}

.refresh-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.refresh-icon {
  width: 13px;
  height: 13px;
  transition: transform 0.3s;
}

.refresh-icon.spinning {
  animation: spin 1s linear infinite;
}

/* --- Transitions --- */
.suggestions-fade-enter-active,
.suggestions-fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.suggestions-fade-enter-from,
.suggestions-fade-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

.chip-enter-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.chip-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.chip-enter-from {
  opacity: 0;
  transform: translateY(8px) scale(0.95);
}
.chip-leave-to {
  opacity: 0;
  transform: scale(0.9);
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}
</style>
