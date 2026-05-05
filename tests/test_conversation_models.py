"""Tests for Conversation and Message models."""

import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
django.setup()

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

    def test_conversation_str_empty_title(self):
        conv = Conversation.objects.create()
        assert "Conversation" in str(conv)

    def test_create_message(self):
        conv = Conversation.objects.create(title="Test")
        msg = Message.objects.create(
            conversation=conv, role="user", content="What is ML?"
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

    def test_message_str(self):
        conv = Conversation.objects.create(title="Test")
        msg = Message.objects.create(
            conversation=conv,
            role="user",
            content="What is machine learning and how does it work?",
        )
        assert str(msg).startswith("user:")

    def test_conversation_cascade_delete(self):
        conv = Conversation.objects.create(title="Test")
        Message.objects.create(conversation=conv, role="user", content="Q")
        Message.objects.create(conversation=conv, role="assistant", content="A")
        conv_id = conv.id
        conv.delete()
        assert not Message.objects.filter(conversation_id=conv_id).exists()
