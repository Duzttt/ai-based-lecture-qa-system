## 2024-05-15 - Missing ARIA labels on refresh buttons
**Learning:** Found multiple instances in `AdminDashboard.vue` and `DocumentsTab.vue` where the refresh button (`<button class="refresh-btn">↻</button>`) was an icon-only button without an accessible label, making it unreadable by screen readers.
**Action:** Added context-specific `aria-label` and `title` attributes (e.g. `aria-label="Refresh documents"`) to all `.refresh-btn` components. Next time, always check icon-only buttons for missing ARIA labels and ensure tooltips are used where context is ambiguous.
