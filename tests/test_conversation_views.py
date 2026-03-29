"""Tests for conversation CRUD views."""

import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
django.setup()

from django.test import TestCase, Client
from django_app.models import Conversation, Message


class TestConversationViews(TestCase):
    def setUp(self):
        self.client = Client()

    def test_create_conversation(self):
        response = self.client.post(
            "/api/conversations/create", {}, content_type="application/json"
        )
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

    def test_list_conversations_pagination(self):
        for i in range(5):
            Conversation.objects.create(title=f"Conv {i}")
        response = self.client.get("/api/conversations?page=1&per_page=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) == 2
        assert data["total"] == 5
        assert data["pages"] == 3

    def test_get_conversation(self):
        conv = Conversation.objects.create(title="Test")
        Message.objects.create(conversation=conv, role="user", content="Hello")
        Message.objects.create(conversation=conv, role="assistant", content="Hi!")
        response = self.client.get(f"/api/conversations/{conv.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test"
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][1]["role"] == "assistant"

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

    def test_delete_conversation_not_found(self):
        response = self.client.delete("/api/conversations/nonexistent-id/delete")
        assert response.status_code == 404
