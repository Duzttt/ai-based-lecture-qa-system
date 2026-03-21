"""
Django models for the Lecture Note Q&A System.
"""

from django.db import models


class SuggestedQuestion(models.Model):
    """
    Model to store generated question suggestions and track their usage.
    
    This model stores questions that were suggested to users based on
    selected documents, along with statistics about their usage.
    """
    
    # Question types
    QUESTION_TYPE_CHOICES = [
        ("concept", "Concept/Definition"),
        ("method", "Method/Process"),
        ("comparison", "Comparison"),
        ("reason", "Reason/Explanation"),
        ("example", "Example/Application"),
    ]
    
    # The question text
    question_text = models.TextField(
        help_text="The suggested question text"
    )
    
    # Question type/category
    question_type = models.CharField(
        max_length=20,
        choices=QUESTION_TYPE_CHOICES,
        default="concept",
        help_text="Type of question (concept, method, comparison, etc.)"
    )
    
    # Associated notebook (if using notebooks feature)
    notebook = models.ForeignKey(
        "Notebook",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="suggested_questions",
        help_text="Associated notebook (optional)"
    )
    
    # Documents this suggestion was generated from
    # Using a text field to store document names/IDs as comma-separated values
    # This is simpler than a M2M for this use case
    document_names = models.TextField(
        help_text="Comma-separated list of document names this was generated from"
    )
    
    # Tracking statistics
    click_count = models.IntegerField(
        default=0,
        help_text="Number of times this suggestion was clicked"
    )
    
    feedback_score = models.FloatField(
        null=True,
        blank=True,
        help_text="User feedback score (if collected)"
    )
    
    # Metadata about generation
    generation_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata about question generation"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this suggestion was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When this suggestion was last updated"
    )
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["question_type"]),
            models.Index(fields=["click_count"]),
        ]
    
    def __str__(self) -> str:
        return f"{self.question_type}: {self.question_text[:50]}..."
    
    def increment_click_count(self) -> None:
        """Increment the click count and save."""
        self.click_count += 1
        self.save(update_fields=["click_count", "updated_at"])
    
    def set_feedback(self, score: float) -> None:
        """Set user feedback score."""
        self.feedback_score = score
        self.save(update_fields=["feedback_score", "updated_at"])


class Notebook(models.Model):
    """
    Model to represent a collection/notebook of documents.
    
    This is a simple notebook model that can be used to group
    documents together for organized Q&A sessions.
    """
    
    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Name of the notebook"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Description of the notebook"
    )
    
    # Store document names as comma-separated values
    document_names = models.TextField(
        default="",
        blank=True,
        help_text="Comma-separated list of document names in this notebook"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-created_at"]
    
    def __str__(self) -> str:
        return self.name
    
    def get_documents(self) -> list:
        """Get list of document names."""
        if not self.document_names:
            return []
        return [name.strip() for name in self.document_names.split(",") if name.strip()]
    
    def add_document(self, document_name: str) -> None:
        """Add a document to the notebook."""
        docs = self.get_documents()
        if document_name not in docs:
            docs.append(document_name)
            self.document_names = ", ".join(docs)
            self.save(update_fields=["document_names", "updated_at"])
    
    def remove_document(self, document_name: str) -> None:
        """Remove a document from the notebook."""
        docs = self.get_documents()
        if document_name in docs:
            docs.remove(document_name)
            self.document_names = ", ".join(docs)
            self.save(update_fields=["document_names", "updated_at"])


class QueryLog(models.Model):
    """
    Model to log and track all queries made to the RAG system.
    
    Used for analytics, debugging, and performance monitoring.
    """

    # Query types for categorization
    QUERY_TYPE_CHOICES = [
        ("concept", "Concept/Definition"),
        ("method", "Method/Process"),
        ("comparison", "Comparison"),
        ("reason", "Reason/Explanation"),
        ("example", "Example/Application"),
        ("other", "Other"),
    ]

    # The query text
    query = models.TextField(
        help_text="The user's query text"
    )

    # Query type/category (can be auto-detected or manually set)
    query_type = models.CharField(
        max_length=20,
        choices=QUERY_TYPE_CHOICES,
        default="other",
        help_text="Type of query"
    )

    # Performance metrics
    latency_ms = models.IntegerField(
        help_text="Query latency in milliseconds"
    )

    cache_hit = models.BooleanField(
        default=False,
        help_text="Whether the result was served from cache"
    )

    results_count = models.IntegerField(
        default=0,
        help_text="Number of results returned"
    )

    # Retrieval details
    top_k = models.IntegerField(
        default=3,
        help_text="Top-K parameter used for retrieval"
    )

    similarity_threshold = models.FloatField(
        default=0.6,
        help_text="Similarity threshold used"
    )

    # Retrieved documents (store as JSON for reference)
    retrieved_documents = models.JSONField(
        default=list,
        blank=True,
        help_text="List of retrieved document references"
    )

    # User feedback (optional)
    user_feedback = models.BooleanField(
        null=True,
        blank=True,
        help_text="User feedback: True=helpful, False=not helpful"
    )

    # Session/user tracking (optional)
    session_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Session identifier"
    )

    # LLM response info
    llm_model = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="LLM model used for generation"
    )

    answer_length = models.IntegerField(
        default=0,
        help_text="Length of generated answer in characters"
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the query was made"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["query_type"]),
            models.Index(fields=["cache_hit"]),
            models.Index(fields=["latency_ms"]),
        ]

    def __str__(self) -> str:
        return f"{self.query_type}: {self.query[:50]}... ({self.latency_ms}ms)"


class SystemMetric(models.Model):
    """
    Model to store system performance metrics over time.
    
    Used for monitoring and creating performance charts.
    """

    # Metric types
    METRIC_TYPE_CHOICES = [
        ("avg_latency", "Average Latency"),
        ("p95_latency", "P95 Latency"),
        ("query_count", "Query Count"),
        ("cache_hit_rate", "Cache Hit Rate"),
        ("embedding_time", "Embedding Time"),
        ("retrieval_time", "Retrieval Time"),
        ("index_size", "Index Size"),
        ("chunk_count", "Chunk Count"),
        ("document_count", "Document Count"),
        ("memory_usage", "Memory Usage"),
        ("disk_usage", "Disk Usage"),
        ("similarity_score", "Similarity Score"),
    ]

    name = models.CharField(
        max_length=50,
        choices=METRIC_TYPE_CHOICES,
        help_text="Metric name"
    )

    value = models.FloatField(
        help_text="Metric value"
    )

    # Additional metadata (e.g., unit, labels)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metric metadata"
    )

    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="When the metric was recorded"
    )

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["name", "-timestamp"]),
            models.Index(fields=["-timestamp"]),
        ]

    def __str__(self) -> str:
        return f"{self.name}: {self.value} @ {self.timestamp}"


class ConfigHistory(models.Model):
    """
    Model to track configuration changes over time.
    
    Provides audit trail and ability to rollback configurations.
    """

    # Configuration categories
    CONFIG_CATEGORY_CHOICES = [
        ("retrieval", "Retrieval Parameters"),
        ("chunking", "Chunking Parameters"),
        ("model", "Model Selection"),
        ("advanced", "Advanced Options"),
    ]

    category = models.CharField(
        max_length=20,
        choices=CONFIG_CATEGORY_CHOICES,
        default="retrieval",
        help_text="Configuration category"
    )

    # The configuration values (stored as JSON)
    config = models.JSONField(
        help_text="Configuration values"
    )

    # Previous configuration (for rollback)
    previous_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Previous configuration values"
    )

    # Who made the change
    changed_by = models.CharField(
        max_length=100,
        default="system",
        help_text="Who made the change"
    )

    # Reason for the change
    reason = models.TextField(
        blank=True,
        default="",
        help_text="Reason for the configuration change"
    )

    # Whether this config is currently active
    is_active = models.BooleanField(
        default=False,
        help_text="Whether this is the active configuration"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the change was made"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["category", "-created_at"]),
            models.Index(fields=["-created_at"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.category} config by {self.changed_by} @ {self.created_at}"

    @classmethod
    def get_active_config(cls, category: str) -> dict:
        """Get the active configuration for a category."""
        active = cls.objects.filter(
            category=category,
            is_active=True
        ).first()
        return active.config if active else {}
