# Success Measurement, LLM Summarizer, and Reasoning Display Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement three features: (1) success measurement that works with local Ollama, (2) enable LLM-based document summarization in Studio panel, and (3) show thinking process in chat panel only for reasoning models.

**Architecture:**
- Success measurement: Add query feedback mechanism tracking user satisfaction via upvote/downvote on answers
- LLM Summarizer: Enable the disabled `_call_llm()` method in summarizer.py to use local LLM for summarization
- Reasoning display: Check if model supports thinking via existing `_model_supports_thinking()`, show thinking in chat when available

**Tech Stack:** Django, Vue.js, Ollama, sentence-transformers, FAISS

---

## Task 1: Add Success Measurement (Query Feedback)

**Files:**
- Modify: `django_app/models.py:155-296` - Add success measurement fields to QueryLog
- Modify: `django_app/views/rag.py:36-90` - Add vote endpoint
- Modify: `django_backend/urls.py` - Add vote URL route
- Test: `tests/test_query_vote.py`

### Task 1A: Add feedback model fields and API endpoint

**Step 1: Write the failing test**

Create `tests/test_query_vote.py`:

```python
import pytest
from django.test import Client
from django_app.models import QueryLog


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def sample_query_log(db):
    return QueryLog.objects.create(
        query_text="What is machine learning?",
        answer_text="Machine learning is...",
        llm_provider="local_llm",
        llm_model="qwen3",
        llm_status=200,
    )


def test_upvote_query_success(client, sample_query_log):
    """Test upvoting a query increases its feedback score."""
    response = client.post(f'/api/query/{sample_query_log.id}/vote', {
        'vote': 'up'
    })
    assert response.status_code == 200
    sample_query_log.refresh_from_db()
    assert sample_query_log.user_feedback is True


def test_downvote_query_success(client, sample_query_log):
    """Test downvoting a query sets feedback to False."""
    response = client.post(f'/api/query/{sample_query_log.id}/vote', {
        'vote': 'down'
    })
    assert response.status_code == 200
    sample_query_log.refresh_from_db()
    assert sample_query_log.user_feedback is False


def test_get_query_with_vote_status(client, sample_query_log):
    """Test getting query includes vote status."""
    sample_query_log.user_feedback = True
    sample_query_log.save()
    response = client.get(f'/api/query/{sample_query_log.id}')
    assert response.status_code == 200
    data = response.json()
    assert data['user_feedback'] is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_query_vote.py::test_upvote_query_success -v`
Expected: FAIL with 404 (endpoint not found)

**Step 3: Add vote endpoint to django_app/views/rag.py**

Add after `ask_question` function (around line 90):

```python
@csrf_exempt
def query_vote_view(request, query_id):
    """Vote on a query answer (upvote/downvote for success measurement)."""
    if request.method != 'POST':
        return _error_response("Only POST allowed", status=405)

    try:
        query_log = QueryLog.objects.get(id=query_id)
    except QueryLog.DoesNotExist:
        return _error_response("Query not found", status=404)

    body = _get_json_body(request)
    vote = body.get('vote', '').lower()

    if vote not in ('up', 'down'):
        return _error_response("Vote must be 'up' or 'down'", status=400)

    query_log.user_feedback = (vote == 'up')
    query_log.save()

    return JsonResponse({
        'query_id': query_log.id,
        'user_feedback': query_log.user_feedback,
        'message': 'Vote recorded'
    })
```

**Step 4: Add URL route in django_backend/urls.py**

Add to urlpatterns:

```python
path('query/<int:query_id>/vote', rag.query_vote_view, name='query_vote'),
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_query_vote.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add django_app/views/rag.py django_backend/urls.py tests/test_query_vote.py
git commit -m "feat: add query voting endpoint for success measurement"
```

---

## Task 2: Enable LLM Summarization in Studio Panel

**Files:**
- Modify: `app/services/summarizer.py:143-144` - Enable LLM summarization
- Modify: `django_app/views/summary.py` - Add summary API endpoint
- Modify: `django_backend/urls.py` - Add summary URL
- Test: `tests/test_summarizer.py`

### Task 2A: Enable LLM summarization

**Step 1: Write failing test**

Create `tests/test_summarizer.py`:

```python
import pytest
from app.services.summarizer import DocumentSummarizer


def test_summarizer_uses_llm(monkeypatch):
    """Test that summarizer calls LLM when enabled."""
    call_count = 0

    def mock_call_llm(**kwargs):
        nonlocal call_count
        call_count += 1
        return "Mock summary"

    monkeypatch.setattr('app.services.summarizer.call_llm', mock_call_llm)

    summarizer = DocumentSummarizer(llm_provider='local_llm')
    result = summarizer.summarize(
        documents=[{'name': 'test.pdf', 'text': 'This is a test document about AI.'}],
        config={'length': 'short', 'style': 'bullets'}
    )

    assert call_count > 0, "LLM should be called"
    assert 'summary' in result or 'text' in result
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_summarizer.py::test_summarizer_uses_llm -v`
Expected: FAIL with "LLM summarization is temporarily disabled"

**Step 3: Enable LLM in summarizer.py**

Replace line 143-144 in `app/services/summarizer.py`:

```python
def _call_llm(self, prompt: str, response_format: str = None) -> str:
    """Call local LLM for summarization."""
    return self._call_local_llm(prompt, response_format)
```

Also update the `summarize()` method to call `_call_llm` (find and update the method around lines 320+):

```python
def summarize(self, documents, config=None):
    config = config or {}
    use_llm = config.get('use_llm', True)  # Default to LLM

    if not documents:
        raise SummarizerError("No documents provided")

    if len(documents) == 1:
        result = self.generate_single_doc_summary(documents[0], config)
        if use_llm:
            # Try LLM generation, fall back to extractive on failure
            try:
                llm_summary = self._call_llm(
                    self._build_prompt(documents, config),
                    config.get('response_format')
                )
                if llm_summary:
                    result['text'] = llm_summary
            except SummarizerError:
                pass  # Keep extractive result
        return result
    else:
        result = self.generate_multi_doc_summary(documents, config)
        if use_llm:
            try:
                llm_summary = self._call_llm(
                    self._build_prompt(documents, config),
                    config.get('response_format')
                )
                if llm_summary:
                    result['text'] = llm_summary
            except SummarizerError:
                pass
        return result
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_summarizer.py::test_summarizer_uses_llm -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/services/summarizer.py
git commit -m "feat: enable LLM-based document summarization"
```

---

## Task 3: Show Thinking Process in Chat Panel (Reasoning Models Only)

**Files:**
- Modify: `app/services/local_rag.py` - Return thinking when using reasoning model
- Modify: `app/services/llm_client.py` - Ensure thinking is returned properly
- Modify: `frontend/src/components/chat/ChatPanel.vue` - Display thinking UI
- Modify: `frontend/src/components/chat/ChatMessage.vue` - Render thinking content
- Test: `frontend/tests/chat.test.js`

### Task 3A: Verify thinking is returned from backend

**Step 1: Check existing reasoning model detection**

The codebase already has `_model_supports_thinking()` in `app/services/llm_client.py:30-43`.

Add test `tests/test_reasoning.py`:

```python
import pytest
from app.services.llm_client import _model_supports_thinking


def test_reasoning_models_detected():
    """Test reasoning models are detected correctly."""
    assert _model_supports_thinking("deepseek-r1") is True
    assert _model_supports_thinking("deepseek-r1:14b") is True
    assert _model_supports_thinking("qwen3") is True
    assert _model_supports_thinking("qwen3:4b") is True


def test_non_reasoning_models_not_detected():
    """Test non-reasoning models return False."""
    assert _model_supports_thinking("llama2") is False
    assert _model_supports_thinking("mistral") is False
    assert _model_supports_thinking("gpt-4") is False
```

**Step 2: Run tests**

Run: `pytest tests/test_reasoning.py -v`
Expected: PASS (function already exists)

### Task 3B: Display thinking in ChatPanel

**Step 1: Add thinking display component**

Update `frontend/src/components/chat/ChatMessage.vue` to show thinking:

```vue
<script setup>
import { computed } from 'vue'

const props = defineProps({
  reasoning: {
    type: String,
    default: ''
  },
  showThinking: {
    type: Boolean,
    default: false
  }
})

const displayThinking = computed(() => {
  if (!props.reasoning) return false
  return props.showThinking
})
</script>

<template>
  <div v-if="displayThinking" class="thinking-container">
    <div class="thinking-header">
      <span class="thinking-label">Thinking</span>
    </div>
    <pre class="thinking-content">{{ reasoning }}</pre>
  </div>
</template>

<style scoped>
.thinking-container {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 8px;
  border-left: 3px solid #4f46e5;
}
.thinking-header {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}
.thinking-content {
  white-space: pre-wrap;
  font-family: monospace;
  font-size: 13px;
  color: #374151;
  margin: 0;
}
</style>
```

**Step 2: Update ChatPanel to track showThinking**

Add this computed in `ChatPanel.vue`:

```javascript
// Check if current model supports thinking
const showThinking = computed(() => {
  const model = settings.model?.toLowerCase() || ''
  const reasoningModels = ['deepseek-r1', 'qwen3', 'qwen2.5']
  return reasoningModels.some(m => model.includes(m))
})
```

Then pass to ChatMessage:

```vue
<ChatMessage
  v-for="msg in messages"
  :key="msg.id"
  :content="msg.content"
  :role="msg.role"
  :reasoning="msg.reasoning"
  :show-thinking="showThinking"
  :sentences="msg.sentences"
  :sources="msg.sources"
/>
```

**Step 3: Run frontend tests (if exist)**

Run: `npm test -- ChatPanel`
Expected: PASS

**Step 4: Commit**

```bash
git add frontend/src/components/chat/ChatMessage.vue frontend/src/components/chat/ChatPanel.vue
git commit -m "feat: display thinking process for reasoning models in chat"
```

---

## Final Verification

After completing all tasks, run:

```bash
pytest tests/test_query_vote.py tests/test_summarizer.py tests/test_reasoning.py -v
```

Verify:
- Query voting works (up/down)
- LLM summarization is called (not extractive-only)
- Reasoning models show thinking, normal models don't

---

### Plan complete and saved to `docs/plans/2026-04-18-success-measurement-summarize-thinking.md`

**Two execution options:**

1. **Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

2. **Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**