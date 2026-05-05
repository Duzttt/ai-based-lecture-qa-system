"""
Django views package - split into logical modules.

All views are re-exported here for backward compatibility with urls.py.
"""

# Pages
from django_app.views.pages import (
    root,
    index_page,
    app_page,
    chat_demo_page,
    health_check,
)

# Documents
from django_app.views.documents import (
    upload_index_status,
    upload_pdf,
    list_files,
    list_documents,
    delete_document,
    summarize_doc,
    generate_podcast,
)

# RAG / Chat
from django_app.views.rag import (
    ask_question,
    ask_qwen,
    ask_with_citations,
    settings_handler,
    providers_handler,
    llm_health_handler,
    get_rag_config,
    update_rag_config,
    reset_faiss_index,
    chat_htmx,
    retrieve_chunks,
    compare_documents,
)

# Dashboard
from django_app.views.dashboard import (
    dashboard_stats,
    dashboard_metrics,
    dashboard_chunks_distribution,
    dashboard_similarity_distribution,
    dashboard_documents_timeline,
    dashboard_update_config,
    dashboard_reindex,
)

# Admin
from django_app.views.admin import (
    admin_stats,
    admin_query_stats,
    admin_debug_retrieval,
    admin_documents,
    admin_document_chunks,
    admin_delete_document,
    admin_reindex_document,
    admin_indexing_status,
    admin_ab_tests,
    admin_ab_test_create,
    admin_ab_test_start,
    admin_ab_test_stop,
    admin_ab_test_record,
    admin_ab_test_results,
)

# Analytics
from django_app.views.analytics import (
    admin_document_analytics,
    admin_query_clusters,
    admin_failure_analysis,
    admin_embedding_visualization,
    admin_chunk_quality,
    admin_retrieval_trace,
)

# Embedding Models
from django_app.views.embeddings import (
    list_embedding_models,
    get_current_embedding_model,
    switch_embedding_model,
    test_embedding_model,
    get_embedding_model_metrics,
    clear_embedding_model_cache,
)

# Summaries
from django_app.views.summaries import (
    generate_summary,
    get_summary_history,
    delete_summary,
    regenerate_summary,
)

# Suggestions
from django_app.views.suggestions import (
    get_question_suggestions,
    record_suggestion_click,
    get_suggestion_history,
)

# Conversations
from django_app.views.conversations import (
    create_conversation,
    list_conversations,
    get_conversation,
    delete_conversation,
)

# LLM Logs
from django_app.views.llm_logs import (
    llm_logs_list,
    llm_logs_stats,
    llm_logs_page,
)

# Smart Operations
from django_app.views.ops import (
    admin_alerts_current,
    admin_alerts_acknowledge,
    admin_capacity_forecast,
    admin_selfhealing_events,
    admin_selfhealing_config,
    admin_cost_analysis,
    admin_user_behavior,
    admin_generate_report,
    admin_reports_history,
    admin_health_score,
)

__all__ = [
    # Pages
    "root",
    "index_page",
    "app_page",
    "chat_demo_page",
    "health_check",
    # Documents
    "upload_index_status",
    "upload_pdf",
    "list_files",
    "list_documents",
    "delete_document",
    "summarize_doc",
    "generate_podcast",
    # RAG / Chat
    "ask_question",
    "ask_qwen",
    "ask_with_citations",
    "settings_handler",
    "providers_handler",
    "llm_health_handler",
    "get_rag_config",
    "update_rag_config",
    "reset_faiss_index",
    "chat_htmx",
    "retrieve_chunks",
    "compare_documents",
    # Dashboard
    "dashboard_stats",
    "dashboard_metrics",
    "dashboard_chunks_distribution",
    "dashboard_similarity_distribution",
    "dashboard_documents_timeline",
    "dashboard_update_config",
    "dashboard_reindex",
    # Admin
    "admin_stats",
    "admin_query_stats",
    "admin_debug_retrieval",
    "admin_documents",
    "admin_document_chunks",
    "admin_delete_document",
    "admin_reindex_document",
    "admin_indexing_status",
    "admin_ab_tests",
    "admin_ab_test_create",
    "admin_ab_test_start",
    "admin_ab_test_stop",
    "admin_ab_test_record",
    "admin_ab_test_results",
    # Analytics
    "admin_document_analytics",
    "admin_query_clusters",
    "admin_failure_analysis",
    "admin_embedding_visualization",
    "admin_chunk_quality",
    "admin_retrieval_trace",
    # Embedding Models
    "list_embedding_models",
    "get_current_embedding_model",
    "switch_embedding_model",
    "test_embedding_model",
    "get_embedding_model_metrics",
    "clear_embedding_model_cache",
    # Summaries
    "generate_summary",
    "get_summary_history",
    "delete_summary",
    "regenerate_summary",
    # Suggestions
    "get_question_suggestions",
    "record_suggestion_click",
    "get_suggestion_history",
    # LLM Logs
    "llm_logs_list",
    "llm_logs_stats",
    "llm_logs_page",
    # Smart Operations
    "admin_alerts_current",
    "admin_alerts_acknowledge",
    "admin_capacity_forecast",
    "admin_selfhealing_events",
    "admin_selfhealing_config",
    "admin_cost_analysis",
    "admin_user_behavior",
    "admin_generate_report",
    "admin_reports_history",
    "admin_health_score",
    # Conversations
    "create_conversation",
    "list_conversations",
    "get_conversation",
    "delete_conversation",
]
