# Vue.js Frontend UI Polish — Design Document

**Date:** 2026-03-30
**Scope:** Comprehensive visual, layout, and interactivity improvements to the Vue.js frontend

## Context

The root `index.html` prototype features a polished "Academic Curator" design with glassmorphism, Material Symbols icons, and a cohesive indigo dark theme. The Vue.js frontend (37 components) has not been aligned with this design language. Issues include emoji icons mixed with SVGs, duplicate CSS tokens, mixed Chinese/English text, native browser dialogs, and missing accessibility attributes.

## Section 1: Icon System & Color Alignment

### 1a. Unified Icon System

Replace all emoji icons and inconsistent SVG references with **Material Symbols Outlined** (same library used in the prototype).

**Changes:**

| File | Location | Current | Replacement |
|---|---|---|---|
| `Topbar.vue` | Line 21 | 🛠️ Admin | `material-symbols-outlined` icon `admin_panel_settings` |
| `Topbar.vue` | Line 25 | 📊 Chunks | `material-symbols-outlined` icon `analytics` |
| `Topbar.vue` | Line 29 | ⚙️ Settings | `material-symbols-outlined` icon `settings` |
| `ChatMessage.vue` | Line 28 | 👤 / 🤖 emojis | `material-symbols-outlined` icons `person` / `smart_toy` |

**Action:** Add Google Fonts Material Symbols `<link>` to `frontend/index.html` head.

### 1b. Color Token Alignment

The Vue app defines 10 Tailwind colors in `tailwind.config.js` that duplicate CSS custom properties in `style.css`. Consolidate:

- **Tailwind tokens remain the source of truth** — remove duplicate CSS custom properties from `style.css` lines 7-16
- **Add accent palette tokens** to `tailwind.config.js` matching the prototype's indigo scheme: `accent`, `accent-container`, `accent-on`
- **Update all components** to use Tailwind classes (`bg-bg-panel`, `text-accent`) instead of raw hex values scattered across scoped styles

### 1c. Language Consistency

- `StudioPanel.vue:14-17`: Chinese titles → English: "文档摘要" → "Summarize", "测验" → "Quiz", "闪卡" → "Flashcards", "播客" → "Podcast"
- `SummaryModal.vue:42`: Default language from `zh` to `en`

## Section 2: Toast Notifications & Chat UX

### 2a. Toast Notification System

Replace all native `alert()` and `confirm()` with a lightweight toast system.

**New files:**
- `frontend/src/components/shared/Toast.vue` — toast container + individual toast component
- `frontend/src/stores/toastStore.js` — Pinia store with `showToast(type, message)`

**Toast spec:**
- Position: top-right, stacked vertically with 8px gap
- Types: `success` (green), `error` (red), `info` (blue), `warning` (amber)
- Behavior: auto-dismiss after 3 seconds, manual dismiss via close button
- Animation: slide-in from right, fade-out on dismiss

**Replacements:**

| File | Line | Current | New |
|---|---|---|---|
| `StudioPanel.vue` | 34 | `alert('coming soon')` | `toast.info('Quiz generation coming soon')` |
| `SourcesPanel.vue` | 103 | `confirm('Delete?')` | Custom styled confirmation dialog or toast |
| `ComparisonView.vue` | 80 | `alert('Saved!')` | `toast.success('Comparison saved')` |

### 2b. Chat Input — Multiline Support

`ChatInput.vue` uses `<input type="text">` with no multiline capability.

**Changes:**
- Replace `<input>` with auto-resizing `<textarea>` (starts at 1 row, grows to max 5 rows)
- **Enter** = send message, **Shift+Enter** = insert new line
- Add optional character counter (2000 char soft limit)
- Remove duplicate `@keydown.enter.prevent` handler (lines 28-31 and `handleKeyPress` lines 12-17 are redundant)

### 2c. Auto-scroll Chat

`ChatMessageList.vue` does not auto-scroll on new messages.

**Changes:**
- Add invisible `div` ref at bottom of message list
- `watch(messages, () => scrollToBottom())` with `{ deep: true }`
- Add "Scroll to bottom" floating button visible when user scrolls up >200px from bottom
- Button style: small pill, positioned bottom-center of chat area

### 2d. Chat Avatar Icons

Replace emoji avatars in `ChatMessage.vue:28`:
- User: `<span class="material-symbols-outlined">person</span>` inside a 28px accent-colored circle
- Assistant: `<span class="material-symbols-outlined">smart_toy</span>` inside a 28px subtle-bg circle

## Section 3: Accessibility, Z-Index & CSS Cleanup

### 3a. Accessibility (A11y)

Add `aria-label`, `role`, and keyboard support to all interactive elements:

| Component | Change |
|---|---|
| `Topbar.vue` — all buttons | `aria-label="Admin"`, `aria-label="View chunks"`, `aria-label="Settings"` |
| `ChatInput.vue` — send button | `aria-label="Send message"` |
| `SourcesPanel.vue` — file list items | `role="listitem"`, `tabindex="0"` |
| `StudioPanel.vue` — tool cards | `role="button"`, `aria-label` per tool (e.g., "Summarize document") |
| `CitationAnswer.vue` — tooltips | `tabindex="0"`, show on focus in addition to hover |
| All modal components | `role="dialog"`, `aria-modal="true"`, focus trap, close on Escape key |

### 3b. Z-Index Strategy

Define a z-index scale in `tailwind.config.js`:

```js
zIndex: {
  'panel': '1',       // Sidebars, chat area
  'header': '50',     // Topbar
  'overlay': '100',   // Modal backdrops
  'modal': '110',     // Modal content
  'toast': '200',     // Toast notifications
  'tooltip': '300',   // Citation tooltips
}
```

Apply to existing components:
- App.vue shell panels: `z-panel`
- Topbar.vue: `z-header`
- SummaryModal, ChunkViz, SettingsModal: backdrop `z-overlay`, content `z-modal`
- New Toast.vue: `z-toast`
- CitationAnswer.vue tooltip: `z-tooltip`

### 3c. CSS Cleanup

1. **Remove duplicate `@keyframes spin`** from `RetrievalChunks.vue`, `ChatPanel.vue`, `ComparisonView.vue` — centralize in `style.css`
2. **Remove duplicate CSS custom properties** from `style.css` lines 7-16 — use Tailwind tokens only
3. **Add Firefox scrollbar support** in `style.css`:
   ```css
   * {
     scrollbar-width: thin;
     scrollbar-color: rgba(255,255,255,0.15) transparent;
   }
   ```

### 3d. Dead Button Fix

- `Topbar.vue:34` — Notification button has no handler. Hide with `v-if="false"` or wire up later.

## Files Modified

| File | Changes |
|---|---|
| `frontend/index.html` | Add Material Symbols `<link>` |
| `frontend/tailwind.config.js` | Add accent palette, z-index scale |
| `frontend/src/style.css` | Remove duplicate vars, add Firefox scrollbars, centralize keyframes |
| `frontend/src/components/layout/Topbar.vue` | Icon swap, aria-labels, notification button |
| `frontend/src/components/layout/SourcesPanel.vue` | Replace confirm(), aria attributes |
| `frontend/src/components/layout/StudioPanel.vue` | Fix language, replace alert(), aria attributes |
| `frontend/src/components/chat/ChatInput.vue` | Multiline textarea, remove duplicate handler |
| `frontend/src/components/chat/ChatMessage.vue` | Avatar icons |
| `frontend/src/components/chat/ChatMessageList.vue` | Auto-scroll, scroll-to-bottom button |
| `frontend/src/components/chat/CitationAnswer.vue` | Z-tooltip, focus tooltip |
| `frontend/src/components/shared/Toast.vue` | **New** — toast component |
| `frontend/src/stores/toastStore.js` | **New** — toast Pinia store |

## Out of Scope

- Markdown rendering in chat messages
- Message persistence across page refresh
- Streaming/typewriter effect for responses
- PDF.js bundling (still CDN)
- Vue Router integration
- Mobile responsive redesign
