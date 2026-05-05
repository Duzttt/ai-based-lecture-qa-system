"""Tests for ConversationService."""

import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
django.setup()

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

    def test_add_message_sets_title(self):
        conv = self.service.create_conversation()
        assert conv.title == ""
        self.service.add_message(conv, "user", "What is machine learning?")
        conv.refresh_from_db()
        assert conv.title != ""

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

    def test_rewrite_query_no_history(self):
        conv = self.service.create_conversation()
        # No history, should return original even with pronouns
        result = self.service.rewrite_query("What about it?", conv)
        assert result == "What about it?"

    @patch("app.services.conversation_service._call_llm_for_rewrite")
    def test_rewrite_query_with_pronouns(self, mock_llm):
        mock_llm.return_value = "What are the disadvantages of machine learning?"
        conv = self.service.create_conversation()
        self.service.add_message(conv, "user", "What is machine learning?")
        self.service.add_message(conv, "assistant", "ML is a subset of AI...")
        result = self.service.rewrite_query("What about its disadvantages?", conv)
        assert "disadvantages" in result.lower()
        assert "machine learning" in result.lower()

    @patch("app.services.conversation_service._call_llm_for_rewrite")
    def test_rewrite_query_fallback_on_failure(self, mock_llm):
        mock_llm.side_effect = Exception("LLM error")
        conv = self.service.create_conversation()
        self.service.add_message(conv, "user", "What is ML?")
        result = self.service.rewrite_query("What about it?", conv)
        assert result == "What about it?"  # Falls back to original

    @patch("app.services.conversation_service._call_llm_for_rewrite")
    def test_rewrite_query_fallback_on_short_result(self, mock_llm):
        mock_llm.return_value = "OK"
        conv = self.service.create_conversation()
        self.service.add_message(conv, "user", "What is ML?")
        result = self.service.rewrite_query("What about it?", conv)
        assert result == "What about it?"  # Falls back because result too short

    def test_generate_conversation_title(self):
        title = self.service.generate_conversation_title(
            "What is machine learning and how does it work?"
        )
        assert len(title) <= 50
        assert len(title) > 0

    def test_generate_conversation_title_short(self):
        title = self.service.generate_conversation_title("What is ML?")
        assert title == "What is ML?"

    def test_format_history_for_prompt(self):
        conv = self.service.create_conversation()
        self.service.add_message(conv, "user", "What is ML?")
        self.service.add_message(conv, "assistant", "ML is a subset of AI.")
        history = self.service.get_recent_messages(conv)
        text = self.service.format_history_for_prompt(history)
        assert "User: What is ML?" in text
        assert "Assistant: ML is a subset of AI." in text
