## 2024-05-18 - Missing ARIA Controls on Collapsible Sections
**Learning:** Found an accessibility issue where collapsible sections (like the "Reasoning" dropdown in ChatMessage) were toggled via buttons using `aria-expanded`, but lacked `aria-controls` to programmatically associate the button with the collapsible content. This prevents screen readers from understanding which section is being toggled.
**Action:** Always pair `aria-expanded` with `aria-controls` on toggle buttons. Ensure the controlled container has a matching `id` (using dynamically generated IDs if rendered in a list).
