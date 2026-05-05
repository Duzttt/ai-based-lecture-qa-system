# Postman Test Collection Design

## Overview

Create a separate Postman test collection for automated API testing covering core flows with basic happy path + error cases.

## Core Flows & Coverage

| Flow | Endpoints | Happy Path | Error Cases |
|------|----------|-----------|-----------|------------|
| Document Upload | `POST /api/upload` | 200 + upload status | 400 (invalid file), 413 (too large), 415 (wrong type) |
| Chat | `POST /api/chat` | 200 + answer | 400 (empty query), 404 (missing index), 503 (LLM unavailable) |
| Summarize | `POST /api/summarize` | 200 + summary | 400 (no docs), 404 (doc not found) |
| Settings | `GET/PUT /api/settings` | 200 + config | 400 (invalid config), 404 (config not found) |

## Collection Structure

```
RAG Test Collection/
├── Setup/
│   ├── Health Check
│   └── LLM Health Check
├── Document Upload/
│   ├── Upload PDF (success)
│   ├── Upload Invalid Type (415)
│   ├── Upload Too Large (413)
│   ├── Upload Empty (400)
├── Chat/
│   ├── Ask Question (success)
│   ├── Ask Empty Query (400)
│   ├── Ask No Index (404)
│   ├── Ask LLM Unavailable (503)
├── Summarize/
│   ├── Summarize Doc (success)
│   ├── Summarize No Docs (400)
│   ├── Summarize Not Found (404)
├── Settings/
│   ├── Get Settings (success)
│   ├── Update Settings (success)
│   ├── Update Invalid Config (400)
```

## Test Assertions

### Happy Path Template
```javascript
pm.test('Status code is 200', () => {
  pm.response.to.have.status(200);
});
const data = pm.response.json();
pm.test('Response has required fields', () => {
  pm.expect(data.answer || data.summary || data.provider).to.exist;
});
```

### Error Path Template
```javascript
pm.test('Status code is 400', () => {
  pm.response.to.have.status(400);
});
const data = pm.response.json();
pm.test('Error response has detail', () => {
  pm.expect(data.detail).to.be.a('string');
});
```

## Variables

| Variable | Description | Example |
|----------|------------|---------|
| `{{baseUrl}}` | API base URL | `http://localhost:8000` |
| `{{testPdfPath}}` | Path to test PDF | `./tests/fixtures/sample.pdf` |
| `{{llmProvider}}` | Test LLM provider | `local_llm` |

## Test Data

- `tests/fixtures/sample.pdf` — Valid PDF for upload tests
- `tests/fixtures/empty.pdf` — Empty file for edge case
- `tests/fixtures/wrong.txt` — Wrong extension for 415 test

## Execution

**Run all tests:** `newman run RAG-Test-Collection.json`

**Run single flow:** `newman run RAG-Test-Collection.json --folder "Chat"`

## Design Approved

- Core flows: document upload, chat, summarize, settings
- Coverage: Happy path + error cases (400/404/500)
- Separate collection from production API