# LLM Provider Quick Switch - Design Document

## Overview

Add a dropdown selector in the TopBar for quickly switching LLM provider and model
without opening the settings modal. Uses a Pinia store for global state management
and a new backend endpoint to expose available providers.

## Motivation

Currently switching LLM provider requires: clicking Settings button → changing
dropdown → typing model name → clicking Save. This is slow for frequent switching.
A one-click dropdown in the TopBar reduces this to a single click.

## Architecture

### Backend Changes

#### 1. Extend VALID_PROVIDERS

**File:** `django_app/views/helpers.py:13`

Change `VALID_PROVIDERS = {"gemini", "openrouter"}` to include `local_qwen`.

#### 2. Fix _build_runtime_llm_settings

**File:** `django_app/views/helpers.py:250-271`

Add `local_qwen` branch: use `settings.LOCAL_QWEN_MODEL` as default model,
no API key required.

#### 3. Fix settings_handler GET

**File:** `django_app/views/rag.py:244-266`

Add `local_qwen` branch in the GET handler to return correct default model.

#### 4. New Endpoint: GET /api/settings/providers

**File:** `django_app/views/rag.py` (new function `providers_handler`)

Returns:
```json
{
  "current": {"provider": "openrouter", "model": "openrouter/free"},
  "providers": [
    {
      "id": "gemini",
      "name": "Google Gemini",
      "models": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
      "requires_api_key": true,
      "has_api_key": true
    },
    {
      "id": "openrouter",
      "name": "OpenRouter",
      "models": ["openrouter/free", "anthropic/claude-3-haiku", "meta-llama/llama-3-70b-instruct"],
      "requires_api_key": true,
      "has_api_key": true
    },
    {
      "id": "local_qwen",
      "name": "Local Qwen (llama.cpp)",
      "models": [" ", " ", "qwen2.5:3b", "qwen3.5:4b"],
      "requires_api_key": false,
      "has_api_key": false
    }
  ]
}
```

**Route:** `django_backend/urls.py` add `path("api/settings/providers", views.providers_handler)`

### Frontend Changes

#### 5. API Function

**File:** `frontend/src/services/api.js`

Add `getProviders()` calling `GET /api/settings/providers`.

#### 6. Pinia Store: llmSettingsStore

**File:** `frontend/src/stores/llmSettingsStore.js` (new)

State: `currentProvider`, `currentModel`, `providers`, `isSwitching`, `error`

Actions:
- `loadProviders()` — fetch from `/api/settings/providers`, populate state
- `switchProvider(providerId, model)` — POST to `/api/settings`, update local state

#### 7. ProviderSwitcher Component

**File:** `frontend/src/components/settings/ProviderSwitcher.vue` (new)

- Compact dropdown button showing current provider icon + name
- Click to expand: grouped list of providers → models
- Selecting a model triggers `switchProvider()` with loading indicator
- Visual feedback: success toast, error inline display
- Style: matches existing pill-btn design in TopBar

#### 8. TopBar Integration

**File:** `frontend/src/components/layout/Topbar.vue`

- Import and render `<ProviderSwitcher />` in `topbar-center` area
- Keep existing Settings button for advanced config (API keys, etc.)

#### 9. App.vue Initialization

**File:** `frontend/src/App.vue`

- Import `llmSettingsStore`, call `loadProviders()` in `onMounted`

## Data Flow

```
App.vue onMounted
  → llmSettingsStore.loadProviders()
    → GET /api/settings/providers
    → populate store.providers, store.currentProvider, store.currentModel

User clicks dropdown → selects model
  → llmSettingsStore.switchProvider(providerId, model)
    → POST /api/settings {provider, model}
    → backend writes data/settings.json
    → store updates currentProvider/currentModel
    → subsequent /api/chat requests use new provider
```

## File Change Summary

| File | Action | Description |
|------|--------|-------------|
| `django_app/views/helpers.py` | Modify | Add local_qwen to VALID_PROVIDERS, fix _build_runtime_llm_settings |
| `django_app/views/rag.py` | Modify | Add providers_handler, fix settings_handler for local_qwen |
| `django_app/views/__init__.py` | Modify | Export providers_handler |
| `django_backend/urls.py` | Modify | Add /api/settings/providers route |
| `frontend/src/services/api.js` | Modify | Add getProviders() |
| `frontend/src/stores/llmSettingsStore.js` | Create | Pinia store for LLM settings |
| `frontend/src/components/settings/ProviderSwitcher.vue` | Create | Dropdown component |
| `frontend/src/components/layout/Topbar.vue` | Modify | Add ProviderSwitcher |
| `frontend/src/App.vue` | Modify | Initialize store on mount |

## Testing

- Manual: switch between all 3 providers via dropdown, verify chat uses correct provider
- Backend: verify GET /api/settings/providers returns correct data
- Backend: verify POST /api/settings with local_qwen works
- Frontend: verify dropdown shows correct current selection after page reload
