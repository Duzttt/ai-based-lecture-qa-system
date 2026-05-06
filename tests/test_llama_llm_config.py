import pytest
from unittest.mock import patch, MagicMock
from app.services.llama_llm_config import configure_llm, LLMConfigError


def test_configure_llm_unsupported_provider():
    """不支持的provider应抛出LLMConfigError"""
    with pytest.raises(LLMConfigError, match="Unsupported LLM provider"):
        configure_llm(provider="unknown_provider")


def test_configure_llm_local_sets_settings():
    """配置local provider应设置Settings.llm为OpenAILike实例"""
    mock_local_instance = MagicMock()
    mock_local_class = MagicMock(return_value=mock_local_instance)

    with (
        patch("app.services.llama_llm_config.OpenAILike", mock_local_class),
        patch("app.services.llama_llm_config.Settings") as mock_settings,
    ):
        configure_llm(
            provider="local",
            model="qwen2.5:3b",
            base_url="http://localhost:8080/v1",
        )
        assert mock_settings.llm == mock_local_instance

    mock_local_class.assert_called_once()
    call_kwargs = mock_local_class.call_args.kwargs
    assert call_kwargs.get("model") == "qwen2.5:3b"
    assert call_kwargs.get("api_base") == "http://localhost:8080/v1"


def test_configure_llm_local_default_model():
    """local provider未指定model时应使用默认值"""
    mock_local_instance = MagicMock()
    mock_local_class = MagicMock(return_value=mock_local_instance)

    with (
        patch("app.services.llama_llm_config.OpenAILike", mock_local_class),
        patch("app.services.llama_llm_config.Settings"),
    ):
        configure_llm(provider="local")

    call_kwargs = mock_local_class.call_args.kwargs
    assert call_kwargs.get("model") == "qwen2.5:3b"


def test_configure_llm_local_default_base_url():
    """local provider未指定base_url时应使用默认值"""
    mock_local_instance = MagicMock()
    mock_local_class = MagicMock(return_value=mock_local_instance)

    with (
        patch("app.services.llama_llm_config.OpenAILike", mock_local_class),
        patch("app.services.llama_llm_config.Settings"),
    ):
        configure_llm(provider="local")

    call_kwargs = mock_local_class.call_args.kwargs
    assert call_kwargs.get("api_base") == "http://localhost:8080/v1"


def test_configure_llm_gemini_with_mock():
    """使用mock测试gemini provider配置"""
    mock_gemini_instance = MagicMock()
    mock_gemini_class = MagicMock(return_value=mock_gemini_instance)

    with (
        patch("app.services.llama_llm_config.Gemini", mock_gemini_class),
        patch("app.services.llama_llm_config.Settings") as mock_settings,
    ):
        configure_llm(
            provider="gemini",
            model="gemini-2.0-flash",
            api_key="test_key",
        )
        assert mock_settings.llm == mock_gemini_instance

    mock_gemini_class.assert_called_once()
    call_kwargs = mock_gemini_class.call_args
    assert call_kwargs.kwargs.get("model") == "gemini-2.0-flash"


def test_configure_llm_gemini_default_model():
    """gemini provider未指定model时应使用默认值"""
    mock_gemini_instance = MagicMock()
    mock_gemini_class = MagicMock(return_value=mock_gemini_instance)

    with (
        patch("app.services.llama_llm_config.Gemini", mock_gemini_class),
        patch("app.services.llama_llm_config.Settings"),
    ):
        configure_llm(provider="gemini", api_key="test_key")

    call_kwargs = mock_gemini_class.call_args
    assert call_kwargs.kwargs.get("model") == "gemini-2.0-flash"


def test_configure_llm_gemini_unavailable():
    """Gemini不可用时应抛出LLMConfigError"""
    with patch("app.services.llama_llm_config.Gemini", None):
        with pytest.raises(LLMConfigError, match="Gemini LLM not available"):
            configure_llm(provider="gemini", api_key="test_key")


def test_configure_llm_openrouter_with_mock():
    """使用mock测试openrouter provider配置"""
    mock_openrouter_instance = MagicMock()
    mock_openrouter_class = MagicMock(return_value=mock_openrouter_instance)

    with (
        patch("app.services.llama_llm_config.OpenRouter", mock_openrouter_class),
        patch("app.services.llama_llm_config.Settings") as mock_settings,
    ):
        configure_llm(
            provider="openrouter",
            model="anthropic/claude-3-haiku",
            api_key="test_key",
        )
        assert mock_settings.llm == mock_openrouter_instance

    mock_openrouter_class.assert_called_once()


def test_configure_llm_openrouter_unavailable():
    """OpenRouter不可用时应抛出LLMConfigError"""
    with patch("app.services.llama_llm_config.OpenRouter", None):
        with pytest.raises(LLMConfigError, match="OpenRouter LLM not available"):
            configure_llm(provider="openrouter", api_key="test_key")


def test_configure_llm_local_unavailable():
    """OpenAILike不可用时应抛出LLMConfigError"""
    with patch("app.services.llama_llm_config.OpenAILike", None):
        with pytest.raises(LLMConfigError, match="OpenAILike LLM not available"):
            configure_llm(provider="local")
