from typing import Optional

from llama_index.core import Settings

try:
    from llama_index.llms.gemini import Gemini
except ImportError:
    Gemini = None

try:
    from llama_index.llms.openrouter import OpenRouter
except ImportError:
    OpenRouter = None

try:
    from llama_index.llms.openai_like import OpenAILike
except ImportError:
    OpenAILike = None


class LLMConfigError(Exception):
    pass


def configure_llm(
    provider: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    **kwargs,
) -> None:
    """
    配置LlamaIndex LLM设置

    Args:
        provider: LLM提供商 (gemini, openrouter, local)
        model: 模型名称
        api_key: API密钥
        base_url: API基础URL
        **kwargs: 其他参数
    """
    if provider == "gemini":
        if Gemini is None:
            raise LLMConfigError(
                "Gemini LLM not available. Install llama-index-llms-gemini"
            )
        Settings.llm = Gemini(
            model=model or "gemini-2.0-flash", api_key=api_key, **kwargs
        )

    elif provider == "openrouter":
        if OpenRouter is None:
            raise LLMConfigError(
                "OpenRouter LLM not available. Install llama-index-llms-openrouter"
            )
        Settings.llm = OpenRouter(
            model=model or "anthropic/claude-3-haiku", api_key=api_key, **kwargs
        )

    elif provider == "local":
        if OpenAILike is None:
            raise LLMConfigError(
                "OpenAILike LLM not available. Install llama-index-llms-openai-like"
            )
        Settings.llm = OpenAILike(
            model=model or "qwen2.5:3b",
            api_base=base_url or "http://localhost:8080/v1",
            api_key="not-needed",
            **kwargs,
        )

    else:
        raise LLMConfigError(f"Unsupported LLM provider: {provider}")
