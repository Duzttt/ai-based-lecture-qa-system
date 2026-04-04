# Multi-Turn Conversation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add multi-turn conversation support with context understanding, enabling follow-up question handling and LLM-based query rewriting.

**Architecture:** DB-backed conversation storage with LLM query rewriting. New Conversation/Message Django models, ConversationService for history management and query rewriting, modified /api/chat/citations endpoint to support conversation_id, and new conversation CRUD endpoints.

**Tech Stack:** Django, Django ORM, existing LLM client (llm_client.py), UUID primary keys, JSONField for source storage

---

### Task 1: Add Conversation and Message Django Models

**Files:**
- Modify: `django_app/models.py` (add after existing models)
- Create: Migration file (auto-generated)

**Step 1: Write the failing test**

```python
# tests/test_conversation_models.py
import pytest
from django.test import TestCase
from django_app.models import Conversation, Message

class TestConversationModel(TestCase):
    def test_create_conversation(self):
        conv = Conversation.objects.create(title="Test")
        assert conv.id is not None
        assert conv.title == "Test"
        assert conv.created_at is not None

    def test_conversation_str(self):
        conv = Conversation.objects.create(title="Machine Learning Basics")
        assert str(conv) == "Machine Learning Basics"

    def test_create_message(self):
        conv = Conversation.objects.create(title="Test")
        msg = Message.objects.create(
            conversation=conv,
            role="user",
            content="What is ML?"
        )
        assert msg.id is not None
        assert msg.role == "user"
        assert msg.conversation == conv

    def test_message_ordering(self):
        conv = Conversation.objects.create(title="Test")
        msg1 = Message.objects.create(conversation=conv, role="user", content="Q1")
        msg2 = Message.objects.create(conversation=conv, role="assistant", content="A1")
        messages = list(conv.messages.all())
        assert messages[0].id == msg1.id
        assert messages[1].id == msg2.id

    def test_message_sources_default(self):
        conv = Conversation.objects.create(title="Test")
        msg = Message.objects.create(conversation=conv, role="user", content="Q")
        assert msg.sources == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_conversation_models.py -v`
Expected: FAIL with "cannot import name 'Conversation'"

**Step 3: Add models to `django_app/models.py`**

```python
import uuid

# Add after existing models:

class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notebook = models.ForeignKey(
        "Notebook", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="conversations"
    )

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title or f"Conversation {self.id}"


class Message(models.Model):
    ROLE_CHOICES = [("user", "User"), ("assistant", "Assistant")]
    id = models.AutoField(primary_key=True)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    sources = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"
```

**Step 4: Run migration**

Run: `python manage.py makemigrations django_app && python manage.py migrate`

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_conversation_models.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add django_app/models.py tests/test_conversation_models.py django_app/migrations/
git commit -m "feat: add Conversation and Message models for multi-turn chat"
```

---

### Task 2: Create ConversationService

**Files:**
- Create: `app/services/conversation_service.py`
- Create: `tests/test_conversation_service.py`

**Step 1: Write the failing tests**

```python
# tests/test_conversation_service.py
import pytest
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django_app.models import Conversation, Message
from app.services.conversation_service import ConversationService

class TestConversationService(TestCase):
    def setUp(self):
        self.service = ConversationService()

    def test_create_conversation(self):
        conv = self.service.create_conversation()
        assert conv.id is not None
        assert conv.title == ""

    def test_get_or_create_new(self):
        conv = self.service.get_or_create_conversation(None)
        assert conv.id is not None

    def test_get_or_create_existing(self):
        conv1 = self.service.create_conversation()
        conv2 = self.service.get_or_create_conversation(str(conv1.id))
        assert conv1.id == conv2.id

    def test_get_or_create_invalid_id(self):
        conv = self.service.get_or_create_conversation("invalid-uuid")
        assert conv.id is not None  # Creates new conversation

    def test_add_message(self):
        conv = self.service.create_conversation()
        msg = self.service.add_message(conv, "user", "What is ML?")
        assert msg.role == "user"
        assert msg.content == "What is ML?"

    def test_add_message_with_sources(self):
        conv = self.service.create_conversation()
        sources = [{"source": "doc.pdf", "page": 1, "text": "..."}]
        msg = self.service.add_message(conv, "assistant", "ML is...", sources=sources)
        assert msg.sources == sources

    def test_get_recent_messages_empty(self):
        conv = self.service.create_conversation()
        messages = self.service.get_recent_messages(conv)
        assert messages == []

    def test_get_recent_messages_with_history(self):
        conv = self.service.create_conversation()
        self.service.add_message(conv, "user", "Q1")
        self.service.add_message(conv, "assistant", "A1")
        self.service.add_message(conv, "user", "Q2")
        messages = self.service.get_recent_messages(conv)
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Q1"

    def test_get_recent_messages_window_limit(self):
        conv = self.service.create_conversation()
        for i in range(12):  # 6 turns = 12 messages
            role = "user" if i % 2 == 0 else "assistant"
            self.service.add_message(conv, role, f"Message {i}")
        messages = self.service.get_recent_messages(conv, max_turns=5)
        assert len(messages) == 10  # 5 turns = 10 messages
        assert messages[0]["content"] == "Message 2"  # First 2 messages truncated

    def test_rewrite_query_standalone(self):
        conv = self.service.create_conversation()
        result = self.service.rewrite_query("What is machine learning?", conv)
        assert result == "What is machine learning?"

    @patch("app.services.conversation_service.call_llm")
    def test_rewrite_query_with_pronouns(self, mock_llm):
        mock_llm.return_value = "What are the disadvantages of machine learning?"
        conv = self.service.create_conversation()
        self.service.add_message(conv, "user", "What is machine learning?")
        self.service.add_message(conv, "assistant", "ML is a subset of AI...")
        result = self.service.rewrite_query("What about its disadvantages?", conv)
        assert "disadvantages" in result.lower()
        assert "machine learning" in result.lower()

    @patch("app.services.conversation_service.call_llm")
    def test_rewrite_query_fallback_on_failure(self, mock_llm):
        mock_llm.side_effect = Exception("LLM error")
        conv = self.service.create_conversation()
        self.service.add_message(conv, "user", "What is ML?")
        result = self.service.rewrite_query("What about it?", conv)
        assert result == "What about it?"  # Falls back to original

    def test_generate_conversation_title(self):
        title = self.service.generate_conversation_title("What is machine learning and how does it work?")
        assert len(title) <= 50
        assert len(title) > 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_conversation_service.py -v`
Expected: FAIL with "cannot import name 'ConversationService'"

**Step 3: Write the implementation**

```python
# app/services/conversation_service.py
import re
import uuid
from typing import Optional
from django_app.models import Conversation, Message
from app.services.llm_client import call_llm


class ConversationService:
    """Manages conversation history and query rewriting for multi-turn chat."""

    PRONOUN_PATTERN = re.compile(
        r'\b(its?|it|this|that|these|those|they|them|their|the above|the previous|'
        r'它|它的|这个|那个|这些|那些|他们|他们的|上述|之前)\b',
        re.IGNORECASE
    )

    def create_conversation(self, notebook_id: Optional[str] = None) -> Conversation:
        """Create a new conversation session."""
        kwargs = {}
        if notebook_id:
            from django_app.models import Notebook
            try:
                kwargs["notebook"] = Notebook.objects.get(id=notebook_id)
            except Notebook.DoesNotExist:
                pass
        return Conversation.objects.create(**kwargs)

    def get_or_create_conversation(self, conversation_id: Optional[str] = None) -> Conversation:
        """Get existing conversation or create a new one."""
        if not conversation_id:
            return self.create_conversation()
        try:
            return Conversation.objects.get(id=conversation_id)
        except (Conversation.DoesNotExist, ValueError):
            return self.create_conversation()

    def add_message(
        self,
        conversation: Conversation,
        role: str,
        content: str,
        sources: Optional[list] = None
    ) -> Message:
        """Store a message in the conversation history."""
        msg = Message.objects.create(
            conversation=conversation,
            role=role,
            content=content,
            sources=sources or []
        )
        # Update conversation timestamp
        conversation.save()  # triggers auto_now on updated_at
        # Auto-generate title from first user message
        if role == "user" and not conversation.title:
            conversation.title = self.generate_conversation_title(content)
            conversation.save(update_fields=["title"])
        return msg

    def get_recent_messages(self, conversation: Conversation, max_turns: int = 5) -> list[dict]:
        """Get last N messages formatted for LLM context.
        A turn = 1 user message + 1 assistant message = 2 messages.
        """
        max_messages = max_turns * 2
        messages = conversation.messages.all()[:max_messages]
        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

    def _needs_rewriting(self, query: str, conversation: Conversation) -> bool:
        """Check if a query likely needs rewriting (contains pronouns/references)."""
        if not conversation.messages.exists():
            return False
        return bool(self.PRONOUN_PATTERN.search(query))

    def rewrite_query(self, query: str, conversation: Conversation) -> str:
        """Rewrite ambiguous follow-up queries into standalone questions.
        Returns original query if it's already standalone or rewriting fails.
        """
        if not self._needs_rewriting(query, conversation):
            return query

        # Get last 3 messages for context
        recent = list(conversation.messages.order_by("-created_at")[:6])
        recent.reverse()

        history_text = "\n".join(
            f"{'User' if msg.role == 'user' else 'Assistant'}: {msg.content[:200]}"
            for msg in recent
        )

        prompt = (
            "Given the following conversation history, rewrite the user's latest question "
            "as a standalone question that can be understood without the conversation context. "
            "Keep the rewritten question concise. Output ONLY the rewritten question, nothing else.\n\n"
            f"Conversation history:\n{history_text}\n\n"
            f"Latest question: {query}\n\n"
            "Standalone question:"
        )

        try:
            result = call_llm(
                messages=[{"role": "user", "content": prompt}],
                model=None,  # Use default model
                temperature=0.0,
                timeout_seconds=10
            )
            rewritten = result.strip().strip('"').strip("'")
            if rewritten and len(rewritten) > 5:
                return rewritten
            return query
        except Exception:
            return query

    def generate_conversation_title(self, first_question: str) -> str:
        """Auto-generate a short title from the first question."""
        # Simple truncation for now
        title = first_question.strip()
        if len(title) > 50:
            title = title[:47] + "..."
        return title
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_conversation_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/services/conversation_service.py tests/test_conversation_service.py
git commit -m "feat: add ConversationService with history management and query rewriting"
```

---

### Task 3: Create Conversation CRUD Views

**Files:**
- Create: `django_app/views/conversations.py`
- Create: `tests/test_conversation_views.py`
- Modify: `django_backend/urls.py` (add routes)

**Step 1: Write the failing tests**

```python
# tests/test_conversation_views.py
import json
import pytest
from django.test import TestCase, Client
from django_app.models import Conversation, Message

class TestConversationViews(TestCase):
    def setUp(self):
        self.client = Client()

    def test_create_conversation(self):
        response = self.client.post("/api/conversations/create", {}, content_type="application/json")
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["title"] == ""

    def test_list_conversations_empty(self):
        response = self.client.get("/api/conversations")
        assert response.status_code == 200
        data = response.json()
        assert data["conversations"] == []

    def test_list_conversations(self):
        Conversation.objects.create(title="Conv 1")
        Conversation.objects.create(title="Conv 2")
        response = self.client.get("/api/conversations")
        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) == 2

    def test_get_conversation(self):
        conv = Conversation.objects.create(title="Test")
        Message.objects.create(conversation=conv, role="user", content="Hello")
        Message.objects.create(conversation=conv, role="assistant", content="Hi!")
        response = self.client.get(f"/api/conversations/{conv.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test"
        assert len(data["messages"]) == 2

    def test_get_conversation_not_found(self):
        response = self.client.get("/api/conversations/nonexistent-id")
        assert response.status_code == 404

    def test_delete_conversation(self):
        conv = Conversation.objects.create(title="To Delete")
        response = self.client.delete(f"/api/conversations/{conv.id}/delete")
        assert response.status_code == 200
        assert not Conversation.objects.filter(id=conv.id).exists()

    def test_delete_cascades_messages(self):
        conv = Conversation.objects.create(title="Test")
        Message.objects.create(conversation=conv, role="user", content="Q")
        conv_id = conv.id
        self.client.delete(f"/api/conversations/{conv_id}/delete")
        assert not Message.objects.filter(conversation_id=conv_id).exists()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_conversation_views.py -v`
Expected: FAIL with 404 (routes not found)

**Step 3: Write the views**

```python
# django_app/views/conversations.py
import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django_app.models import Conversation, Message


@require_http_methods(["POST"])
def create_conversation(request):
    """Create a new conversation."""
    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        body = {}

    notebook_id = body.get("notebook_id")
    kwargs = {}
    if notebook_id:
        from django_app.models import Notebook
        try:
            kwargs["notebook"] = Notebook.objects.get(id=notebook_id)
        except Notebook.DoesNotExist:
            pass

    conv = Conversation.objects.create(**kwargs)
    return JsonResponse({
        "id": str(conv.id),
        "title": conv.title,
        "created_at": conv.created_at.isoformat(),
    }, status=201)


@require_http_methods(["GET"])
def list_conversations(request):
    """List conversations with pagination."""
    page = int(request.GET.get("page", 1))
    per_page = int(request.GET.get("per_page", 20))

    conversations = Conversation.objects.all()
    paginator = Paginator(conversations, per_page)
    page_obj = paginator.get_page(page)

    return JsonResponse({
        "conversations": [
            {
                "id": str(c.id),
                "title": c.title,
                "message_count": c.messages.count(),
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
            }
            for c in page_obj
        ],
        "total": paginator.count,
        "page": page_obj.number,
        "pages": paginator.num_pages,
    })


@require_http_methods(["GET"])
def get_conversation(request, conversation_id):
    """Get a conversation with all its messages."""
    try:
        conv = Conversation.objects.get(id=conversation_id)
    except (Conversation.DoesNotExist, ValueError):
        return JsonResponse({"detail": "Conversation not found"}, status=404)

    messages = [
        {
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "sources": msg.sources,
            "created_at": msg.created_at.isoformat(),
        }
        for msg in conv.messages.all()
    ]

    return JsonResponse({
        "id": str(conv.id),
        "title": conv.title,
        "messages": messages,
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
    })


@require_http_methods(["DELETE"])
def delete_conversation(request, conversation_id):
    """Delete a conversation and all its messages."""
    try:
        conv = Conversation.objects.get(id=conversation_id)
    except (Conversation.DoesNotExist, ValueError):
        return JsonResponse({"detail": "Conversation not found"}, status=404)

    conv.delete()  # Cascades to messages
    return JsonResponse({"detail": "Conversation deleted"})
```

**Step 4: Add URL routes to `django_backend/urls.py`**

Add these imports and paths:
```python
from django_app.views.conversations import (
    create_conversation,
    list_conversations,
    get_conversation,
    delete_conversation,
)

# Add to urlpatterns:
path("api/conversations", list_conversations, name="list_conversations"),
path("api/conversations/", list_conversations, name="list_conversations_slash"),
path("api/conversations/create", create_conversation, name="create_conversation"),
path("api/conversations/<str:conversation_id>", get_conversation, name="get_conversation"),
path("api/conversations/<str:conversation_id>/", get_conversation, name="get_conversation_slash"),
path("api/conversations/<str:conversation_id>/delete", delete_conversation, name="delete_conversation"),
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_conversation_views.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add django_app/views/conversations.py django_backend/urls.py tests/test_conversation_views.py
git commit -m "feat: add conversation CRUD API endpoints"
```

---

### Task 4: Modify `/api/chat/citations` for Multi-Turn Support

**Files:**
- Modify: `django_app/views/rag.py:176-236` (ask_with_citations view)
- Create: `tests/test_multiturn_citations.py`

**Step 1: Write the failing tests**

```python
# tests/test_multiturn_citations.py
import json
import pytest
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django_app.models import Conversation, Message

class TestMultiTurnCitations(TestCase):
    def setUp(self):
        self.client = Client()

    @patch("django_app.views.rag.CitationRAGPipeline")
    def test_ask_without_conversation_backward_compatible(self, mock_pipeline):
        """Without conversation_id, behavior is unchanged."""
        mock_pipeline.return_value.query.return_value = {
            "sentences": [{"text": "ML is AI", "citations": [1]}],
            "sources": {"1": {"text": "...", "file": "doc.pdf", "page": 1}},
            "retrieved_chunks": []
        }
        response = self.client.post(
            "/api/chat/citations",
            {"query": "What is ML?"},
            content_type="application/json"
        )
        assert response.status_code == 200
        data = response.json()
        assert "conversation_id" not in data

    @patch("django_app.views.rag.CitationRAGPipeline")
    @patch("app.services.conversation_service.ConversationService.rewrite_query")
    def test_ask_with_new_conversation(self, mock_rewrite, mock_pipeline):
        """First question with conversation_id creates conversation."""
        mock_rewrite.return_value = "What is machine learning?"
        mock_pipeline.return_value.query.return_value = {
            "sentences": [{"text": "ML is AI", "citations": [1]}],
            "sources": {"1": {"text": "...", "file": "doc.pdf", "page": 1}},
            "retrieved_chunks": []
        }
        response = self.client.post(
            "/api/chat/citations",
            {"query": "What is ML?", "conversation_id": ""},
            content_type="application/json"
        )
        assert response.status_code == 200
        data = response.json()
        assert "conversation_id" in data
        conv = Conversation.objects.get(id=data["conversation_id"])
        assert conv.messages.count() == 2

    @patch("django_app.views.rag.CitationRAGPipeline")
    @patch("app.services.conversation_service.ConversationService.rewrite_query")
    def test_ask_with_existing_conversation(self, mock_rewrite, mock_pipeline):
        """Follow-up question uses conversation history."""
        mock_rewrite.return_value = "What are the disadvantages of ML?"
        mock_pipeline.return_value.query.return_value = {
            "sentences": [{"text": "Overfitting", "citations": [1]}],
            "sources": {"1": {"text": "...", "file": "doc.pdf", "page": 2}},
            "retrieved_chunks": []
        }
        conv = Conversation.objects.create(title="ML Discussion")
        Message.objects.create(conversation=conv, role="user", content="What is ML?")
        Message.objects.create(conversation=conv, role="assistant", content="ML is...")

        response = self.client.post(
            "/api/chat/citations",
            {"query": "What about its disadvantages?", "conversation_id": str(conv.id)},
            content_type="application/json"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["conversation_id"] == str(conv.id)
        assert data["rewritten_query"] == "What are the disadvantages of ML?"
        assert conv.messages.count() == 4
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_multiturn_citations.py -v`
Expected: FAIL

**Step 3: Modify `ask_with_citations` in `django_app/views/rag.py`**

Key changes:
1. Add import: `from app.services.conversation_service import ConversationService`
2. Extract `conversation_id` from request body
3. If conversation_id present: store user message, rewrite query, get history
4. Pass `retrieved_query` (rewritten or original) to pipeline
5. Pass `conversation_history` to pipeline for context
6. After response: store assistant message, add `conversation_id` and `rewritten_query` to response

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_multiturn_citations.py -v`
Expected: PASS

**Step 5: Run all tests**

Run: `pytest tests/ -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add django_app/views/rag.py tests/test_multiturn_citations.py
git commit -m "feat: add multi-turn conversation support to /api/chat/citations"
```

---

### Task 5: Update CitationRAGPipeline to Include Conversation History

**Files:**
- Modify: `app/services/citation_rag.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_citation_rag.py
from unittest.mock import patch

@patch("app.services.citation_rag.call_llm")
def test_query_with_conversation_history(mock_llm):
    """Pipeline accepts and uses conversation history."""
    mock_llm.return_value = '{"sentences": [{"text": "Answer", "citations": [1]}]}'
    pipeline = CitationRAGPipeline()
    history = [
        {"role": "user", "content": "What is ML?"},
        {"role": "assistant", "content": "ML is AI subset"}
    ]
    result = pipeline.query("What about its disadvantages?", conversation_history=history)
    call_args = mock_llm.call_args
    prompt = call_args[1]["messages"][1]["content"]
    assert "What is ML?" in prompt
```

**Step 2: Modify `_build_citation_prompt()` to include conversation history section**

Add `conversation_history` parameter and inject a `## Previous Conversation` section before `## Reference Materials`.

**Step 3: Modify `query()` to accept and pass `conversation_history`**

**Step 4: Run tests**

Run: `pytest tests/test_citation_rag.py -v`

**Step 5: Commit**

```bash
git add app/services/citation_rag.py tests/test_citation_rag.py
git commit -m "feat: pass conversation history to CitationRAGPipeline prompt"
```

---

### Task 6: Frontend Integration

**Files:**
- Modify: `frontend/src/services/api.js`
- Modify: `frontend/src/components/ChatPanel.vue`

**Step 1: Add conversation API functions to `api.js`**

```javascript
export const createConversation = () =>
  api.post('/conversations/create').then(r => r.data);

export const listConversations = (page = 1, perPage = 20) =>
  api.get(`/conversations?page=${page}&per_page=${perPage}`).then(r => r.data);

export const getConversation = (id) =>
  api.get(`/conversations/${id}`).then(r => r.data);

export const deleteConversation = (id) =>
  api.post(`/conversations/${id}/delete`).then(r => r.data);
```

**Step 2: Update ChatPanel.vue**

- Add `conversationId` ref (initially null)
- Include `conversation_id` in fetch body
- Store returned `conversation_id` after first message
- Add "New Conversation" button to reset
- Optionally restore from localStorage on mount

**Step 3: Commit**

```bash
git add frontend/src/services/api.js frontend/src/components/ChatPanel.vue
git commit -m "feat: integrate multi-turn conversation in frontend"
```

---

### Task 7: Final Verification

**Step 1: Run full test suite**

Run: `pytest tests/ -v`

**Step 2: Run linting**

Run: `ruff check app/ django_app/ django_backend/ manage.py`

**Step 3: Manual testing checklist**

- [ ] POST `/api/chat/citations` without conversation_id works as before
- [ ] POST with conversation_id creates new conversation
- [ ] Follow-up with pronouns gets rewritten query
- [ ] GET `/api/conversations` lists conversations
- [ ] GET `/api/conversations/<id>` shows messages
- [ ] DELETE removes conversation and messages
- [ ] 5-turn history window works
- [ ] LLM rewriting failure falls back gracefully

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete multi-turn conversation with context understanding"
```
