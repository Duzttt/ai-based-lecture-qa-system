"""Conversation CRUD views."""

import json

from django.core.paginator import Paginator
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from django_app.models import Conversation, Message


@csrf_exempt
@require_http_methods(["POST"])
def create_conversation(request: HttpRequest) -> JsonResponse:
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
    return JsonResponse(
        {
            "id": str(conv.id),
            "title": conv.title,
            "created_at": conv.created_at.isoformat(),
        },
        status=201,
    )


@require_http_methods(["GET"])
def list_conversations(request: HttpRequest) -> JsonResponse:
    """List conversations with pagination."""
    page = int(request.GET.get("page", 1))
    per_page = int(request.GET.get("per_page", 20))

    conversations = Conversation.objects.all()
    paginator = Paginator(conversations, per_page)
    page_obj = paginator.get_page(page)

    return JsonResponse(
        {
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
        }
    )


@require_http_methods(["GET"])
def get_conversation(request: HttpRequest, conversation_id: str) -> JsonResponse:
    """Get a conversation with all its messages."""
    try:
        conv = Conversation.objects.get(id=conversation_id)
    except Exception:
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

    return JsonResponse(
        {
            "id": str(conv.id),
            "title": conv.title,
            "messages": messages,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
        }
    )


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_conversation(request: HttpRequest, conversation_id: str) -> JsonResponse:
    """Delete a conversation and all its messages."""
    try:
        conv = Conversation.objects.get(id=conversation_id)
    except Exception:
        return JsonResponse({"detail": "Conversation not found"}, status=404)

    conv.delete()  # Cascades to messages
    return JsonResponse({"detail": "Conversation deleted"})
