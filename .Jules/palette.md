
## 2024-05-01 - Chat Input Loading Feedback
**Learning:** Adding a subtle, animated spinner to primary action buttons (like a chat send button) during async operations provides crucial immediate feedback, preventing user confusion about whether their action was registered, especially when inputs are disabled.
**Action:** Always consider replacing the icon in a primary action button with an animated spinner when an async process is triggered and the button enters a disabled state.
## 2024-05-15 - Missing ARIA labels on refresh buttons
**Learning:** Found multiple instances in `AdminDashboard.vue` and `DocumentsTab.vue` where the refresh button (`<button class="refresh-btn">↻</button>`) was an icon-only button without an accessible label, making it unreadable by screen readers.
**Action:** Added context-specific `aria-label` and `title` attributes (e.g. `aria-label="Refresh documents"`) to all `.refresh-btn` components. Next time, always check icon-only buttons for missing ARIA labels and ensure tooltips are used where context is ambiguous.
## 2024-05-18 - Missing ARIA Controls on Collapsible Sections
**Learning:** Found an accessibility issue where collapsible sections (like the "Reasoning" dropdown in ChatMessage) were toggled via buttons using `aria-expanded`, but lacked `aria-controls` to programmatically associate the button with the collapsible content. This prevents screen readers from understanding which section is being toggled.
**Action:** Always pair `aria-expanded` with `aria-controls` on toggle buttons. Ensure the controlled container has a matching `id` (using dynamically generated IDs if rendered in a list).
## 2024-05-05 - Missing ARIA Labels on Icon-only Buttons
**Learning:** Found multiple instances of icon-only buttons across components (like ChatHeader, ModelComparison, ChunkViz, BidirectionalCitations) missing `aria-label` attributes, which makes them inaccessible to screen readers.
**Action:** Add `aria-label` with descriptive text to these close buttons/icon buttons and ensure consistent focus states for keyboard navigation.
