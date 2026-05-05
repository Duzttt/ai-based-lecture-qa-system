"""Conversation service for multi-turn chat with query rewriting."""

import re
from typing import Optional

from app.config import settings
from app.services.runtime_llm import load_runtime_llm_settings
from django_app.models import Conversation, Message


PRONOUN_PATTERN = re.compile(
    r"\b(its?|it|this|that|these|those|they|them|their|the above|the previous|"
    r"它|它的|这个|那个|这些|那些|他们|他们的|上述|之前)\b",
    re.IGNORECASE,
)


def _call_llm_for_rewrite(prompt: str) -> str:
    """Call LLM for query rewriting. Uses the configured provider."""
    from app.services.llm_client import call_llm

    runtime_settings = load_runtime_llm_settings()
    provider = runtime_settings["provider"] or settings.LLM_PROVIDER

    call_kwargs = {
        "timeout": 15,
        "query_text": prompt[:100],
        "temperature": 0.0,
    }
    if provider == "local_llm":
        call_kwargs["base_url"] = (
            runtime_settings["base_url"] or settings.LOCAL_LLM_BASE_URL
        )
    else:
        call_kwargs["api_key"] = runtime_settings["api_key"]
        call_kwargs["base_url"] = runtime_settings["base_url"]

    return call_llm(
        provider=provider,
        model=runtime_settings["model"] or settings.LOCAL_LLM_MODEL,
        call_type="rewrite",
        messages=[{"role": "user", "content": prompt}],
        **call_kwargs,
    )


class ConversationService:
    """Manages conversation history and query rewriting for multi-turn chat."""

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

    def get_or_create_conversation(
        self, conversation_id: Optional[str] = None
    ) -> Conversation:
        """Get existing conversation or create a new one."""
        if not conversation_id:
            return self.create_conversation()
        try:
            return Conversation.objects.get(id=conversation_id)
        except (Conversation.DoesNotExist, ValueError, Exception):
            return self.create_conversation()

    def add_message(
        self,
        conversation: Conversation,
        role: str,
        content: str,
        sources: Optional[list] = None,
    ) -> Message:
        """Store a message in the conversation history."""
        msg = Message.objects.create(
            conversation=conversation,
            role=role,
            content=content,
            sources=sources or [],
        )
        conversation.save()  # triggers auto_now on updated_at
        if role == "user" and not conversation.title:
            conversation.title = self.generate_conversation_title(content)
            conversation.save(update_fields=["title"])
        return msg

    def get_recent_messages(
        self, conversation: Conversation, max_turns: int = 5
    ) -> list[dict]:
        """Get last N messages formatted for LLM context.
        A turn = 1 user message + 1 assistant message = 2 messages.
        Returns messages in chronological order.
        """
        max_messages = max_turns * 2
        all_messages = conversation.messages.order_by("-id")[:max_messages]
        messages = list(reversed(all_messages))
        return [{"role": msg.role, "content": msg.content} for msg in messages]

    def format_history_for_prompt(self, messages: list[dict]) -> str:
        """Format conversation history as a string for LLM prompts."""
        return "\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in messages
        )

    def _needs_rewriting(self, query: str, conversation: Conversation) -> bool:
        """Check if a query likely needs rewriting (contains pronouns/references)."""
        if not conversation.messages.exists():
            return False
        return bool(PRONOUN_PATTERN.search(query))

    def rewrite_query(self, query: str, conversation: Conversation) -> str:
        """Rewrite ambiguous follow-up queries into standalone questions.
        Returns original query if it's already standalone or rewriting fails.
        """
        if not self._needs_rewriting(query, conversation):
            return query

        recent = list(conversation.messages.order_by("-created_at")[:6])
        recent.reverse()

        history_text = "\n".join(
            f"{'User' if msg.role == 'user' else 'Assistant'}: {msg.content[:200]}"
            for msg in recent
        )

        prompt = (
            "Given the following conversation history, rewrite the user's latest "
            "question as a standalone question that can be understood without the "
            "conversation context. Keep the rewritten question concise. "
            "Output ONLY the rewritten question, nothing else.\n\n"
            f"Conversation history:\n{history_text}\n\n"
            f"Latest question: {query}\n\n"
            "Standalone question:"
        )

        try:
            result = _call_llm_for_rewrite(prompt)
            rewritten = result.strip().strip('"').strip("'")
            if rewritten and len(rewritten) > 5:
                return rewritten
            return query
        except Exception:
            return query

    def generate_conversation_title(self, first_question: str) -> str:
        """Auto-generate a short title from the first question."""
        title = first_question.strip()
        if len(title) > 50:
            title = title[:47] + "..."
        return title
