## 2024-05-05 - Missing ARIA Labels on Icon-only Buttons
**Learning:** Found multiple instances of icon-only buttons across components (like ChatHeader, ModelComparison, ChunkViz, BidirectionalCitations) missing `aria-label` attributes, which makes them inaccessible to screen readers.
**Action:** Add `aria-label` with descriptive text to these close buttons/icon buttons and ensure consistent focus states for keyboard navigation.
