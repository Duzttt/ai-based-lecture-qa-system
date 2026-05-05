# Vue.js Frontend UI Polish Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Comprehensive visual, layout, and interactivity polish for the Vue.js frontend — unified icons, color tokens, toast system, multiline chat input, auto-scroll, accessibility, and CSS cleanup.

**Architecture:** Incremental changes across 14 existing Vue files + 2 new files. Each task is independently testable via the Vite dev server (`npm run dev` in `frontend/`).

**Tech Stack:** Vue 3 (Composition API), Pinia, Tailwind CSS 3.4, Material Symbols (Google Fonts CDN)

**Design Doc:** `docs/plans/2026-03-30-vue-ui-polish-design.md`

---

## Task 1: Add Material Symbols and Tailwind Token Updates

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/tailwind.config.js`
- Modify: `frontend/src/style.css`

**Step 1: Add Material Symbols link to `frontend/index.html`**

Open `frontend/index.html` and add this `<link>` inside `<head>`, after existing `<link>` tags:

```html
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap" rel="stylesheet">
```

**Step 2: Update `tailwind.config.js` with accent palette and z-index scale**

Add to `theme.extend`:

```js
colors: {
  // existing...
  'accent': '#bdc2ff',
  'accent-container': '#818cf8',
  'accent-on': '#131e8c',
},
zIndex: {
  'panel': '1',
  'header': '50',
  'overlay': '100',
  'modal': '110',
  'toast': '200',
  'tooltip': '300',
},
```

**Step 3: Clean up `style.css` — remove duplicate vars, add Firefox scrollbars, centralize keyframes**

Replace the duplicate CSS custom properties block (the `:root` section) with only Tailwind imports and unique utilities:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --spacing-unit: 4px;
  --radius-lg: 10px;
}

body {
  margin: 0;
  padding: 0;
  background: radial-gradient(ellipse at 30% 20%, rgba(99, 102, 241, 0.08), transparent 60%),
              radial-gradient(ellipse at 70% 80%, rgba(139, 92, 246, 0.06), transparent 50%),
              #020617;
  color: #e2e8f0;
  font-family: 'Inter', system-ui, sans-serif;
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
}

* {
  scrollbar-width: thin;
  scrollbar-color: rgba(255,255,255,0.15) transparent;
}

*::-webkit-scrollbar {
  width: 6px;
}
*::-webkit-scrollbar-track {
  background: transparent;
}
*::-webkit-scrollbar-thumb {
  background-color: rgba(255,255,255,0.15);
  border-radius: 4px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
```

**Step 4: Verify dev server starts**

Run: `npm run dev` in `frontend/`
Expected: Server starts without errors, page loads at localhost:5173

**Step 5: Commit**

```bash
git add frontend/index.html frontend/tailwind.config.js frontend/src/style.css
git commit -m "feat: add Material Symbols, accent tokens, z-index scale, Firefox scrollbars"
```

---

## Task 2: Toast Notification System

**Files:**
- Create: `frontend/src/stores/toastStore.js`
- Create: `frontend/src/components/shared/Toast.vue`
- Modify: `frontend/src/App.vue`

**Step 1: Create `toastStore.js`**

```js
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useToastStore = defineStore('toast', () => {
  const toasts = ref([])
  let nextId = 0

  function showToast(type, message, duration = 3000) {
    const id = nextId++
    toasts.value.push({ id, type, message })
    setTimeout(() => {
      dismiss(id)
    }, duration)
  }

  function dismiss(id) {
    toasts.value = toasts.value.filter(t => t.id !== id)
  }

  function success(message) { showToast('success', message) }
  function error(message) { showToast('error', message) }
  function info(message) { showToast('info', message) }
  function warning(message) { showToast('warning', message) }

  return { toasts, showToast, dismiss, success, error, info, warning }
})
```

**Step 2: Create `Toast.vue`**

```vue
<template>
  <div class="toast-container" aria-live="polite">
    <TransitionGroup name="toast">
      <div
        v-for="toast in toastStore.toasts"
        :key="toast.id"
        class="toast"
        :class="toast.type"
        role="alert"
      >
        <span class="material-symbols-outlined toast-icon">{{ iconMap[toast.type] }}</span>
        <span class="toast-message">{{ toast.message }}</span>
        <button class="toast-close" @click="toastStore.dismiss(toast.id)" aria-label="Dismiss">
          <span class="material-symbols-outlined">close</span>
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup>
import { useToastStore } from '../../stores/toastStore'
const toastStore = useToastStore()
const iconMap = {
  success: 'check_circle',
  error: 'error',
  info: 'info',
  warning: 'warning',
}
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: 1rem;
  right: 1rem;
  z-index: 200;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
}
.toast {
  pointer-events: auto;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 10px;
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255,255,255,0.08);
  font-size: 13px;
  max-width: 340px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.4);
}
.toast.success { background: rgba(34,197,94,0.15); border-color: rgba(34,197,94,0.3); }
.toast.error { background: rgba(239,68,68,0.15); border-color: rgba(239,68,68,0.3); }
.toast.info { background: rgba(99,102,241,0.15); border-color: rgba(99,102,241,0.3); }
.toast.warning { background: rgba(245,158,11,0.15); border-color: rgba(245,158,11,0.3); }
.toast-icon { font-size: 18px; }
.toast.success .toast-icon { color: #4ade80; }
.toast.error .toast-icon { color: #f87171; }
.toast.info .toast-icon { color: #818cf8; }
.toast.warning .toast-icon { color: #fbbf24; }
.toast-message { flex: 1; color: #e2e8f0; }
.toast-close {
  background: none;
  border: none;
  color: rgba(255,255,255,0.4);
  cursor: pointer;
  padding: 2px;
  display: flex;
}
.toast-close:hover { color: #fff; }
.toast-enter-active { animation: slideIn 0.25s ease-out; }
.toast-leave-active { animation: slideIn 0.2s ease-in reverse; }
@keyframes slideIn {
  from { transform: translateX(100%); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}
</style>
```

**Step 3: Import Toast into `App.vue`**

Add to the imports section of `App.vue`:

```js
import Toast from './components/shared/Toast.vue'
```

Add `<Toast />` inside the template, after the closing `</aside>` tag (right panel).

**Step 4: Verify toasts render**

Run: `npm run dev`, open browser console, run `document.querySelector('[data-toast-test]')` — or proceed to Task 3 where we'll wire up actual toast calls.

**Step 5: Commit**

```bash
git add frontend/src/stores/toastStore.js frontend/src/components/shared/Toast.vue frontend/src/App.vue
git commit -m "feat: add toast notification system (store + component)"
```

---

## Task 3: Replace alert()/confirm() with Toasts

**Files:**
- Modify: `frontend/src/components/layout/StudioPanel.vue`
- Modify: `frontend/src/components/documents/ComparisonView.vue`
- Modify: `frontend/src/components/layout/SourcesPanel.vue`

**Step 1: Replace alert in `StudioPanel.vue`**

Find the `handleStudioClick` function. Replace the `alert()` call with:

```js
import { useToastStore } from '../../stores/toastStore'
const toast = useToastStore()

function handleStudioClick(opt) {
  if (opt.disabled) {
    toast.info(`${opt.label} coming soon`)
    return
  }
  // ... rest of handler
}
```

**Step 2: Replace alert in `ComparisonView.vue`**

Find the save confirmation `alert()`. Replace with:

```js
import { useToastStore } from '../../stores/toastStore'
const toast = useToastStore()

// Replace alert('Saved!') with:
toast.success('Comparison saved')
```

**Step 3: Replace confirm() in `SourcesPanel.vue`**

Find `confirm('Are you sure...')` in the delete handler. Replace with a simple toast warning and proceed with delete (or keep the native confirm for now if a custom modal is out of scope — but remove the direct flow dependency). At minimum:

```js
// Remove: if (!confirm(...))
// Replace with: auto-delete with toast notification
toast.success('Document deleted')
```

**Step 4: Verify by triggering each action**

Run: `npm run dev`
- Click a disabled studio tool → toast appears
- Save a comparison → success toast
- Delete a document → success toast

**Step 5: Commit**

```bash
git add frontend/src/components/layout/StudioPanel.vue frontend/src/components/documents/ComparisonView.vue frontend/src/components/layout/SourcesPanel.vue
git commit -m "fix: replace native alert/confirm with toast notifications"
```

---

## Task 4: Icon System Unification in Topbar

**Files:**
- Modify: `frontend/src/components/layout/Topbar.vue`

**Step 1: Replace emoji buttons with Material Symbols**

Find the three pill buttons (Admin, Chunks, Settings). Replace emoji text with Material Symbols spans:

```vue
<button class="pill-btn" @click="$emit('open-admin')" aria-label="Admin Dashboard">
  <span class="material-symbols-outlined" style="font-size: 16px;">admin_panel_settings</span>
  <span>Admin</span>
</button>
<button class="pill-btn" @click="$emit('open-chunkviz')" aria-label="View Chunks">
  <span class="material-symbols-outlined" style="font-size: 16px;">analytics</span>
  <span>Chunks</span>
</button>
<button class="pill-btn" @click="$emit('open-settings')" aria-label="Settings">
  <span class="material-symbols-outlined" style="font-size: 16px;">settings</span>
  <span>Settings</span>
</button>
```

**Step 2: Hide dead notification button**

Find the notification bell button. Add `v-if="false"` or wrap in a comment:

```vue
<!-- TODO: Notification system not implemented yet
<button ... aria-label="Notifications">
  <span class="material-symbols-outlined">notifications</span>
</button>
-->
```

**Step 3: Add aria-label to avatar**

```vue
<div class="avatar" aria-label="User profile">
```

**Step 4: Verify buttons render with icons**

Run: `npm run dev`, check topbar shows Material Symbols icons instead of emoji.

**Step 5: Commit**

```bash
git add frontend/src/components/layout/Topbar.vue
git commit -m "feat: unify Topbar icons to Material Symbols, add aria-labels"
```

---

## Task 5: Fix StudioPanel Language and Aria Labels

**Files:**
- Modify: `frontend/src/components/layout/StudioPanel.vue`

**Step 1: Change Chinese titles to English**

Find the `studioOptions` array. Replace Chinese labels:

```js
const studioOptions = [
  { key: 'summary', label: 'Summarize', desc: 'Condense complex papers into abstracts.', icon: 'summarize', disabled: false },
  { key: 'quiz', label: 'Quiz', desc: 'Generate active recall tests.', icon: 'quiz', disabled: true },
  { key: 'flashcards', label: 'Flashcards', desc: 'Convert notes into study cards.', icon: 'style', disabled: true },
  { key: 'podcast', label: 'Podcast', desc: 'Turn lectures into audio summaries.', icon: 'podcasts', disabled: true },
]
```

**Step 2: Add aria-labels to tool cards**

Add `role="button"` and `:aria-label="opt.label"` to each tool card element.

**Step 3: Verify**

Run: `npm run dev`, check Studio panel shows English labels.

**Step 4: Commit**

```bash
git add frontend/src/components/layout/StudioPanel.vue
git commit -m "fix: StudioPanel English labels and aria attributes"
```

---

## Task 6: Chat Input Multiline Support

**Files:**
- Modify: `frontend/src/components/chat/ChatInput.vue`

**Step 1: Replace `<input>` with `<textarea>`**

Change the `<input type="text">` to a `<textarea>` with auto-resize:

```vue
<textarea
  ref="inputEl"
  v-model="query"
  @keydown.enter.exact.prevent="sendMessage"
  @input="autoResize"
  :rows="1"
  placeholder="Type your query... (Shift+Enter for new line)"
  class="chat-textarea"
  aria-label="Chat message input"
></textarea>
```

**Step 2: Add auto-resize logic in script**

```js
const inputEl = ref(null)

function autoResize() {
  const el = inputEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 200) + 'px'
}
```

**Step 3: Add textarea styles**

```css
.chat-textarea {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-main, #e2e8f0);
  font-family: inherit;
  font-size: 14px;
  line-height: 1.5;
  resize: none;
  padding: 8px 12px;
  max-height: 200px;
}
.chat-textarea::placeholder {
  color: rgba(255,255,255,0.35);
}
```

**Step 4: Remove duplicate Enter handler**

Delete the old `handleKeyPress` function if it exists separately from the `@keydown.enter.exact.prevent="sendMessage"` binding.

**Step 5: Verify multiline works**

Run: `npm run dev`, type in chat input, press Shift+Enter for new line, Enter to send.

**Step 6: Commit**

```bash
git add frontend/src/components/chat/ChatInput.vue
git commit -m "feat: multiline chat input with auto-resize and Shift+Enter"
```

---

## Task 7: Chat Auto-scroll

**Files:**
- Modify: `frontend/src/components/chat/ChatMessageList.vue`

**Step 1: Add scroll-to-bottom ref and method**

Add to script setup:

```js
import { ref, watch, nextTick } from 'vue'
const messagesEnd = ref(null)

function scrollToBottom() {
  nextTick(() => {
    messagesEnd.value?.scrollIntoView({ behavior: 'smooth' })
  })
}
```

**Step 2: Watch messages for auto-scroll**

```js
watch(() => props.messages, () => {
  scrollToBottom()
}, { deep: true })
```

**Step 3: Add bottom anchor div in template**

At the end of the message list, before closing `</div>`:

```html
<div ref="messagesEnd"></div>
```

**Step 4: Add scroll-to-bottom floating button**

```vue
<button
  v-if="showScrollButton"
  class="scroll-to-bottom"
  @click="scrollToBottom"
  aria-label="Scroll to bottom"
>
  <span class="material-symbols-outlined">keyboard_arrow_down</span>
</button>
```

Add scroll detection:

```js
const showScrollButton = ref(false)

function handleScroll(e) {
  const { scrollTop, scrollHeight, clientHeight } = e.target
  showScrollButton.value = scrollHeight - scrollTop - clientHeight > 200
}
```

Bind `@scroll="handleScroll"` on the scrollable container.

**Step 5: Style the button**

```css
.scroll-to-bottom {
  position: absolute;
  bottom: 12px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(99, 102, 241, 0.2);
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: 9999px;
  padding: 4px 12px;
  cursor: pointer;
  color: #bdc2ff;
  backdrop-filter: blur(8px);
  z-index: 10;
}
.scroll-to-bottom:hover {
  background: rgba(99, 102, 241, 0.35);
}
```

**Step 6: Verify auto-scroll**

Run: `npm run dev`, send messages and verify auto-scroll. Scroll up manually, verify button appears.

**Step 7: Commit**

```bash
git add frontend/src/components/chat/ChatMessageList.vue
git commit -m "feat: auto-scroll chat with scroll-to-bottom button"
```

---

## Task 8: Chat Message Avatar Icons

**Files:**
- Modify: `frontend/src/components/chat/ChatMessage.vue`

**Step 1: Replace emoji avatars**

Find the avatar display (👤 / 🤖). Replace with:

```vue
<div class="msg-avatar" :class="msg.role">
  <span class="material-symbols-outlined">
    {{ msg.role === 'user' ? 'person' : 'smart_toy' }}
  </span>
</div>
```

**Step 2: Add avatar styles**

```css
.msg-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.msg-avatar .material-symbols-outlined {
  font-size: 16px;
}
.msg-avatar.user {
  background: rgba(99, 102, 241, 0.2);
  color: #bdc2ff;
}
.msg-avatar.assistant {
  background: rgba(255, 255, 255, 0.08);
  color: #94a3b8;
}
```

**Step 3: Verify**

Run: `npm run dev`, send a message and check avatar icons render correctly.

**Step 4: Commit**

```bash
git add frontend/src/components/chat/ChatMessage.vue
git commit -m "feat: replace emoji avatars with Material Symbols icons"
```

---

## Task 9: Z-Index Application

**Files:**
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/components/layout/Topbar.vue`
- Modify: `frontend/src/components/shared/Toast.vue` (already set in Task 2)
- Modify: `frontend/src/components/chat/CitationAnswer.vue`

**Step 1: Apply `z-header` to Topbar**

In `Topbar.vue`, add `z-50` class (or inline style `z-index: 50`) to the header element if not already present. With Tailwind, use `class="z-header"` (our custom token).

**Step 2: Apply `z-tooltip` to CitationAnswer tooltip**

In `CitationAnswer.vue`, find the tooltip element. Set `z-index: 300` or use class `z-tooltip`.

**Step 3: Apply z-overlay/z-modal to modals**

In each modal component (SummaryModal, ChunkViz, SettingsModal), ensure:
- Backdrop overlay: `z-overlay` (z-index: 100)
- Modal content: `z-modal` (z-index: 110)

**Step 4: Verify no overlap issues**

Run: `npm run dev`, open modals, check tooltips, verify correct layering.

**Step 5: Commit**

```bash
git add frontend/src/App.vue frontend/src/components/layout/Topbar.vue frontend/src/components/chat/CitationAnswer.vue
git commit -m "fix: apply z-index strategy across modals, tooltips, and header"
```

---

## Task 10: CSS Cleanup — Remove Duplicates

**Files:**
- Modify: `frontend/src/components/chat/RetrievalChunks.vue`
- Modify: `frontend/src/components/documents/ComparisonView.vue`
- Modify: `frontend/src/components/chat/ChatPanel.vue`

**Step 1: Remove duplicate `@keyframes spin` from each file**

In each file, find and delete the `@keyframes spin` block (it's now centralized in `style.css`).

**Step 2: Verify spinner still works**

Run: `npm run dev`, trigger a loading state (e.g., upload a file) and verify the spinner animation works from the centralized keyframe.

**Step 3: Commit**

```bash
git add frontend/src/components/chat/RetrievalChunks.vue frontend/src/components/documents/ComparisonView.vue frontend/src/components/chat/ChatPanel.vue
git commit -m "chore: centralize @keyframes spin, remove duplicates"
```

---

## Task 11: Accessibility Audit Pass

**Files:**
- Modify: `frontend/src/components/chat/ChatInput.vue` (send button aria-label)
- Modify: `frontend/src/components/layout/SourcesPanel.vue` (list items)
- Modify: `frontend/src/components/layout/StudioPanel.vue` (tool cards)

**Step 1: Add aria-label to ChatInput send button**

```vue
<button aria-label="Send message" ...>
```

**Step 2: Add role/tabindex to SourcesPanel file items**

Add `role="listitem"` and `tabindex="0"` to each document list item.

**Step 3: Add role/button to StudioPanel tool cards**

```vue
<div role="button" tabindex="0" :aria-label="opt.label" ...>
```

**Step 4: Verify with browser accessibility tools**

Run: `npm run dev`, open Chrome DevTools > Lighthouse > Accessibility audit. Run audit and check for improvements.

**Step 5: Commit**

```bash
git add frontend/src/components/chat/ChatInput.vue frontend/src/components/layout/SourcesPanel.vue frontend/src/components/layout/StudioPanel.vue
git commit -m "feat: add aria-labels and keyboard accessibility to interactive elements"
```

---

## Final Verification

Run the full dev server and test all features:

```bash
cd frontend && npm run dev
```

Checklist:
- [ ] Topbar shows Material Symbols icons (no emoji)
- [ ] Toast appears on disabled tool click, comparison save, document delete
- [ ] Chat input supports Shift+Enter for multiline
- [ ] Chat auto-scrolls on new messages
- [ ] Scroll-to-bottom button appears when scrolled up
- [ ] Message avatars show Material Symbols icons
- [ ] Modals layer correctly (no z-index issues)
- [ ] Studio panel shows English labels
- [ ] No console errors from missing CSS keyframes
- [ ] Keyboard navigation works on buttons and cards
