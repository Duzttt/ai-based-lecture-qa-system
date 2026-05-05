# LLM Provider Quick Switch Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a one-click dropdown in the TopBar for switching LLM provider and model

**Architecture:** Pinia store manages LLM state globally, new backend endpoint exposes available providers with preset models, ProviderSwitcher component renders dropdown in TopBar

**Tech Stack:** Vue 3, Pinia, Django, Axios

---

## Task 1: Backend — Extend VALID_PROVIDERS and fix helpers

**Files:**
- Modify: `django_app/views/helpers.py:13`
- Modify: `django_app/views/helpers.py:250-271`

**Step 1: Add local_qwen to VALID_PROVIDERS**

In `django_app/views/helpers.py:13`, change:
```python
VALID_PROVIDERS = {"gemini", "openrouter"}
```
to:
```python
VALID_PROVIDERS = {"gemini", "openrouter", "local_qwen"}
```

**Step 2: Fix _build_runtime_llm_settings for local_qwen**

In `django_app/views/helpers.py:250-271`, change:
```python
def _build_runtime_llm_settings() -> Dict[str, Optional[str]]:
    persisted = _load_persisted_settings()

    provider = persisted.get("provider") or settings.LLM_PROVIDER
    if provider not in VALID_PROVIDERS:
        provider = settings.LLM_PROVIDER

    if provider == "gemini":
        default_model = settings.GEMINI_MODEL
        default_key = settings.GEMINI_API_KEY
    elif provider == "local_qwen":
        default_model = settings.LOCAL_QWEN_MODEL
        default_key = None
    else:
        default_model = "anthropic/claude-3-haiku"
        default_key = settings.OPENROUTER_API_KEY

    model = persisted.get("model") or default_model
    api_key = persisted.get("api_key") or default_key

    return {
        "provider": provider,
        "model": model,
        "api_key": api_key,
    }
```

**Step 3: Run lint check**

Run: `ruff check django_app/views/helpers.py`
Expected: No errors

**Step 4: Commit**

```bash
git add django_app/views/helpers.py
git commit -m "feat: extend VALID_PROVIDERS to include local_qwen"
```

## Task 2: Backend — Fix settings_handler for local_qwen

**Files:**
- Modify: `django_app/views/rag.py:241-308`

**Step 1: Fix settings_handler GET branch for local_qwen**

In `django_app/views/rag.py:250-256`, change the GET handler:
```python
    if request.method == "GET":
        stored_settings = _load_persisted_settings()
        provider = stored_settings.get("provider") or app_settings.LLM_PROVIDER
        if provider not in VALID_PROVIDERS:
            provider = app_settings.LLM_PROVIDER

        if provider == "gemini":
            default_model = app_settings.GEMINI_MODEL
            default_key = app_settings.GEMINI_API_KEY
        elif provider == "local_qwen":
            default_model = app_settings.LOCAL_QWEN_MODEL
            default_key = None
        else:
            default_model = "anthropic/claude-3-haiku"
            default_key = app_settings.OPENROUTER_API_KEY

        model = stored_settings.get("model") or default_model
        api_key = stored_settings.get("api_key") or default_key

        return JsonResponse(
            {
                "provider": provider,
                "model": model,
                "has_api_key": bool(api_key),
            }
        )
```

**Step 2: Run lint check**

Run: `ruff check django_app/views/rag.py`
Expected: No errors

**Step 3: Commit**

```bash
git add django_app/views/rag.py
git commit -m "fix: settings_handler GET supports local_qwen provider"
```

## Task 3: Backend — New providers endpoint

**Files:**
- Create: add `providers_handler` in `django_app/views/rag.py`
- Modify: `django_app/views/__init__.py`
- Modify: `django_backend/urls.py`

**Step 1: Add providers_handler to rag.py**

Add this function after `settings_handler` in `django_app/views/rag.py`:

```python
LLM_PROVIDERS_CATALOG = [
    {
        "id": "gemini",
        "name": "Google Gemini",
        "models": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
        "requires_api_key": True,
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "models": [
            "openrouter/free",
            "anthropic/claude-3-haiku",
            "meta-llama/llama-3-70b-instruct",
            "google/gemma-2-9b-it:free",
        ],
        "requires_api_key": True,
    },
    {
        "id": "local_qwen",
        "name": "Local Qwen (Ollama)",
        "models": [" ", " ", "qwen2.5:3b", "qwen3.5:4b"],
        "requires_api_key": False,
    },
]


@csrf_exempt
@require_http_methods(["GET"])
def providers_handler(request: HttpRequest) -> JsonResponse:
    from app.config import settings as app_settings

    stored_settings = _load_persisted_settings()
    current_provider = stored_settings.get("provider") or app_settings.LLM_PROVIDER
    if current_provider not in VALID_PROVIDERS:
        current_provider = app_settings.LLM_PROVIDER

    current_model = stored_settings.get("model") or ""
    if not current_model:
        if current_provider == "gemini":
            current_model = app_settings.GEMINI_MODEL
        elif current_provider == "local_qwen":
            current_model = app_settings.LOCAL_QWEN_MODEL
        else:
            current_model = "anthropic/claude-3-haiku"

    has_gemini_key = bool(app_settings.GEMINI_API_KEY or stored_settings.get("api_key"))
    has_openrouter_key = bool(app_settings.OPENROUTER_API_KEY or stored_settings.get("api_key"))

    providers = []
    for p in LLM_PROVIDERS_CATALOG:
        entry = {**p}
        if p["id"] == "gemini":
            entry["has_api_key"] = has_gemini_key
        elif p["id"] == "openrouter":
            entry["has_api_key"] = has_openrouter_key
        else:
            entry["has_api_key"] = False
        providers.append(entry)

    return JsonResponse(
        {
            "current": {"provider": current_provider, "model": current_model},
            "providers": providers,
        }
    )
```

**Step 2: Export providers_handler in __init__.py**

In `django_app/views/__init__.py`, add `providers_handler` to the import from `rag` and to `__all__`.

**Step 3: Add URL route**

In `django_backend/urls.py`, add:
```python
path("api/settings/providers", views.providers_handler),
```
near the existing `api/settings` route.

**Step 4: Run lint check**

Run: `ruff check django_app/views/rag.py django_app/views/__init__.py django_backend/urls.py`
Expected: No errors

**Step 5: Commit**

```bash
git add django_app/views/rag.py django_app/views/__init__.py django_backend/urls.py
git commit -m "feat: add GET /api/settings/providers endpoint"
```

## Task 4: Frontend — API function

**Files:**
- Modify: `frontend/src/services/api.js`

**Step 1: Add getProviders function**

Add after `saveSettings` (around line 46):
```javascript
export const getProviders = async () => {
  const response = await api.get('/settings/providers')
  return response.data
}
```

**Step 2: Commit**

```bash
git add frontend/src/services/api.js
git commit -m "feat: add getProviders API function"
```

## Task 5: Frontend — llmSettingsStore

**Files:**
- Create: `frontend/src/stores/llmSettingsStore.js`

**Step 1: Create the Pinia store**

```javascript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getProviders, saveSettings } from '../services/api'

export const useLlmSettingsStore = defineStore('llmSettings', () => {
  const currentProvider = ref('')
  const currentModel = ref('')
  const providers = ref([])
  const isSwitching = ref(false)
  const error = ref(null)

  const currentProviderInfo = computed(() => {
    return providers.value.find(p => p.id === currentProvider.value) || null
  })

  const currentProviderName = computed(() => {
    return currentProviderInfo.value?.name || currentProvider.value
  })

  async function loadProviders() {
    try {
      error.value = null
      const data = await getProviders()
      currentProvider.value = data.current.provider
      currentModel.value = data.current.model
      providers.value = data.providers
    } catch (err) {
      error.value = err.message
      console.error('Failed to load LLM providers:', err)
    }
  }

  async function switchProvider(providerId, model) {
    if (!providerId || !model) {
      error.value = 'Provider and model are required'
      return false
    }

    try {
      isSwitching.value = true
      error.value = null

      await saveSettings({
        llm_provider: providerId,
        model: model,
        api_key: '',
      })

      currentProvider.value = providerId
      currentModel.value = model
      return true
    } catch (err) {
      error.value = err.message
      console.error('Failed to switch LLM provider:', err)
      return false
    } finally {
      isSwitching.value = false
    }
  }

  return {
    currentProvider,
    currentModel,
    providers,
    isSwitching,
    error,
    currentProviderInfo,
    currentProviderName,
    loadProviders,
    switchProvider,
  }
})
```

**Step 2: Commit**

```bash
git add frontend/src/stores/llmSettingsStore.js
git commit -m "feat: add llmSettingsStore Pinia store"
```

## Task 6: Frontend — ProviderSwitcher component

**Files:**
- Create: `frontend/src/components/settings/ProviderSwitcher.vue`

**Step 1: Create the component**

```vue
<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useLlmSettingsStore } from '../../stores/llmSettingsStore'

const store = useLlmSettingsStore()
const isOpen = ref(false)
const switchMessage = ref('')
const switchStatus = ref('')

const PROVIDER_ICONS = {
  gemini: '✨',
  openrouter: '🔗',
  local_qwen: '🏠',
}

const toggle = () => {
  isOpen.value = !isOpen.value
}

const handleSelect = async (providerId, model) => {
  if (providerId === store.currentProvider && model === store.currentModel) {
    isOpen.value = false
    return
  }

  const success = await store.switchProvider(providerId, model)
  if (success) {
    switchStatus.value = 'success'
    switchMessage.value = `Switched to ${providerId}`
  } else {
    switchStatus.value = 'error'
    switchMessage.value = store.error || 'Failed to switch'
  }

  isOpen.value = false
  setTimeout(() => {
    switchMessage.value = ''
    switchStatus.value = ''
  }, 3000)
}

const handleClickOutside = (e) => {
  if (!e.target.closest('.provider-switcher')) {
    isOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<template>
  <div class="provider-switcher">
    <button class="switcher-trigger pill-btn" @click="toggle">
      <span class="switcher-icon">{{ PROVIDER_ICONS[store.currentProvider] || '🤖' }}</span>
      <span class="switcher-label">{{ store.currentProviderName || 'LLM' }}</span>
      <span class="switcher-chevron" :class="{ open: isOpen }">▾</span>
    </button>

    <div v-if="switchMessage" class="switcher-toast" :class="switchStatus">
      {{ switchMessage }}
    </div>

    <div v-if="isOpen" class="switcher-dropdown">
      <div v-if="store.isSwitching" class="switcher-loading">
        Switching...
      </div>
      <template v-else>
        <div
          v-for="provider in store.providers"
          :key="provider.id"
          class="provider-group"
        >
          <div class="provider-group-header">
            <span>{{ PROVIDER_ICONS[provider.id] || '🤖' }}</span>
            <span>{{ provider.name }}</span>
            <span v-if="!provider.has_api_key && provider.requires_api_key" class="no-key-badge">
              No API Key
            </span>
          </div>
          <button
            v-for="model in provider.models"
            :key="model"
            class="model-option"
            :class="{
              active: store.currentProvider === provider.id && store.currentModel === model,
            }"
            @click="handleSelect(provider.id, model)"
          >
            <span class="model-name">{{ model }}</span>
            <span v-if="store.currentProvider === provider.id && store.currentModel === model" class="active-dot">●</span>
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.provider-switcher {
  position: relative;
}

.switcher-trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}

.switcher-icon {
  font-size: 13px;
}

.switcher-label {
  font-size: 12px;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.switcher-chevron {
  font-size: 10px;
  transition: transform 0.2s;
  color: var(--text-muted);
}

.switcher-chevron.open {
  transform: rotate(180deg);
}

.switcher-toast {
  position: absolute;
  top: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 12px;
  white-space: nowrap;
  z-index: 100;
  animation: fadeIn 0.2s ease;
}

.switcher-toast.success {
  background: rgba(34, 197, 94, 0.15);
  border: 1px solid rgba(34, 197, 94, 0.5);
  color: #86efac;
}

.switcher-toast.error {
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.5);
  color: #fecaca;
}

.switcher-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
  min-width: 220px;
  background: rgba(15, 23, 42, 0.95);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 14px;
  box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.8);
  z-index: 999;
  overflow: hidden;
  animation: slideDown 0.2s ease;
}

.switcher-loading {
  padding: 16px;
  text-align: center;
  font-size: 12px;
  color: var(--text-muted);
}

.provider-group {
  padding: 6px 0;
}

.provider-group + .provider-group {
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.provider-group-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.no-key-badge {
  margin-left: auto;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 999px;
  background: rgba(239, 68, 68, 0.15);
  color: #fca5a5;
  text-transform: none;
  letter-spacing: 0;
}

.model-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 7px 14px 7px 30px;
  border: none;
  background: none;
  color: var(--text-main);
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s;
  text-align: left;
}

.model-option:hover {
  background: rgba(255, 255, 255, 0.06);
}

.model-option.active {
  background: rgba(99, 102, 241, 0.12);
  color: #a5b4fc;
}

.model-name {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 11px;
}

.active-dot {
  color: #a855f7;
  font-size: 8px;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(-6px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}
</style>
```

**Step 2: Commit**

```bash
git add frontend/src/components/settings/ProviderSwitcher.vue
git commit -m "feat: add ProviderSwitcher dropdown component"
```

## Task 7: Frontend — Integrate into Topbar and App

**Files:**
- Modify: `frontend/src/components/layout/Topbar.vue`
- Modify: `frontend/src/App.vue`

**Step 1: Add ProviderSwitcher to Topbar**

In `Topbar.vue`, add import and place the component in `topbar-center` before the existing buttons:

```vue
<script setup>
import ProviderSwitcher from '../settings/ProviderSwitcher.vue'

const emit = defineEmits(['open-settings', 'open-admin', 'open-chunkviz'])
</script>
```

In the template, add `<ProviderSwitcher />` as the first item in `topbar-center`:
```html
<div class="topbar-center">
  <ProviderSwitcher />
  <button class="pill-btn admin-btn" @click="emit('open-admin')">
    ...
```

**Step 2: Initialize store in App.vue**

In `App.vue`, add:
```javascript
import { useLlmSettingsStore } from './stores/llmSettingsStore'

const llmStore = useLlmSettingsStore()

onMounted(() => {
  llmStore.loadProviders()
})
```

Make sure `onMounted` is imported from `vue` (it already is if other code uses it, otherwise add it to the import).

**Step 3: Run lint and typecheck**

Run: `ruff check django_app/ django_backend/ && black --check django_app/ django_backend/`
Expected: No errors

**Step 4: Build frontend**

Run: `cd frontend && npm run build`
Expected: Successful build

**Step 5: Commit**

```bash
git add frontend/src/components/layout/Topbar.vue frontend/src/App.vue
git commit -m "feat: integrate ProviderSwitcher into Topbar"
```

## Task 8: Verification

**Step 1: Start backend and test the new endpoint**

Run: `python manage.py runserver 0.0.0.0:8000`
Then: `curl http://localhost:8000/api/settings/providers`
Expected: JSON with providers array and current selection

**Step 2: Test provider switching**

```bash
curl -X POST http://localhost:8000/api/settings \
  -H "Content-Type: application/json" \
  -d '{"provider": "local_qwen", "model": "qwen2.5:3b"}'
```
Expected: `{"success": true, "message": "Settings updated"}`

**Step 3: Verify GET returns updated settings**

```bash
curl http://localhost:8000/api/settings
```
Expected: `{"provider": "local_qwen", "model": "qwen2.5:3b", ...}`

**Step 4: Open frontend and test dropdown**

- Navigate to `http://localhost:8000`
- Click the provider dropdown in TopBar
- Switch between providers/models
- Verify toast message appears on success

**Step 5: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: minor fixes from verification"
```
