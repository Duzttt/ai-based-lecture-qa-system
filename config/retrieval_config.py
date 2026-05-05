"""
Retrieval configuration module.

This module provides configurable parameters for the retrieval system,
including chunking settings, fusion parameters, and performance thresholds.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class ChunkingConfig:
    """Configuration for smart chunking."""

    chunk_size: int = 500  # Target chunk size in characters
    overlap: int = 100  # Overlap size in characters
    min_paragraph_size: int = 100  # Minimum paragraph size before merging
    max_paragraph_size: int = 800  # Maximum paragraph size before splitting
    extract_keywords: bool = True  # Whether to extract keywords
    top_k_keywords: int = 5  # Number of keywords to extract


@dataclass
class RetrievalConfig:
    """Configuration for hybrid retrieval."""

    # Fusion settings
    fusion_method: str = "rrf"  # 'rrf' or 'weighted'
    rrf_k: int = 60  # RRF constant
    alpha: float = 0.3  # Dense retrieval weight for weighted fusion

    # Retrieval settings
    top_k: int = 10  # Default number of results to return
    bm25_top_k: int = 20  # BM25 candidate count
    dense_top_k: int = 20  # Dense retrieval candidate count

    # Embedding settings
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # Performance settings
    use_cache: bool = True
    cache_size: int = 1000
    latency_threshold_ms: float = 200.0  # Target latency threshold


@dataclass
class EvaluationConfig:
    """Configuration for retrieval evaluation."""

    # Metrics to compute
    compute_recall: bool = True
    compute_precision: bool = True
    compute_mrr: bool = True
    compute_ndcg: bool = True

    # Evaluation cutoffs
    recall_at: list = field(default_factory=lambda: [1, 3, 5, 10])
    precision_at: list = field(default_factory=lambda: [1, 3, 5, 10])
    ndcg_at: list = field(default_factory=lambda: [5, 10])

    # Test set settings
    min_relevant_docs: int = 1  # Minimum relevant docs per query


@dataclass
class RetrievalSystemConfig:
    """
    Retrieval system configuration.

    Main configuration class that combines all sub-configurations.
    Provides methods for loading, saving, and validating configuration.

    Attributes:
        chunking: Chunking configuration
        retrieval: Retrieval configuration
        evaluation: Evaluation configuration
    """

    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "chunking": asdict(self.chunking),
            "retrieval": asdict(self.retrieval),
            "evaluation": asdict(self.evaluation),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RetrievalSystemConfig":
        """
        Create configuration from dictionary.

        Args:
            data: Dictionary with configuration values

        Returns:
            RetrievalSystemConfig instance
        """
        config = cls()

        if "chunking" in data:
            for key, value in data["chunking"].items():
                if hasattr(config.chunking, key):
                    setattr(config.chunking, key, value)

        if "retrieval" in data:
            for key, value in data["retrieval"].items():
                if hasattr(config.retrieval, key):
                    setattr(config.retrieval, key, value)

        if "evaluation" in data:
            for key, value in data["evaluation"].items():
                if hasattr(config.evaluation, key):
                    setattr(config.evaluation, key, value)

        return config

    def save(self, path: str) -> None:
        """
        Save configuration to JSON file.

        Args:
            path: File path to save configuration
        """
        config_dir = os.path.dirname(path)
        if config_dir:
            os.makedirs(config_dir, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> "RetrievalSystemConfig":
        """
        Load configuration from JSON file.

        Args:
            path: File path to load configuration

        Returns:
            RetrievalSystemConfig instance
        """
        if not os.path.exists(path):
            return cls()

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls.from_dict(data)

    def validate(self) -> bool:
        """
        Validate configuration values.

        Returns:
            bool: True if configuration is valid

        Raises:
            ValueError: If configuration is invalid
        """
        # Validate chunking config
        if self.chunking.overlap >= self.chunking.chunk_size:
            raise ValueError("overlap must be smaller than chunk_size")

        if self.chunking.min_paragraph_size <= 0:
            raise ValueError("min_paragraph_size must be positive")

        if self.chunking.max_paragraph_size <= self.chunking.min_paragraph_size:
            raise ValueError(
                "max_paragraph_size must be greater than min_paragraph_size"
            )

        # Validate retrieval config
        if not 0 <= self.retrieval.alpha <= 1:
            raise ValueError("alpha must be between 0 and 1")

        if self.retrieval.rrf_k <= 0:
            raise ValueError("rrf_k must be positive")

        if self.retrieval.top_k <= 0:
            raise ValueError("top_k must be positive")

        # Validate evaluation config
        if not self.evaluation.recall_at:
            raise ValueError("recall_at must not be empty")

        if not self.evaluation.precision_at:
            raise ValueError("precision_at must not be empty")

        return True


class ConfigManager:
    """
    Configuration manager.

    Manages retrieval system configuration with support for:
    - Default values
    - File-based persistence
    - Environment variable overrides
    - Runtime updates
    """

    DEFAULT_CONFIG_PATH = "config/retrieval_config.json"

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration manager.

        Args:
            config_path: Path to configuration file (optional)
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config = RetrievalSystemConfig()
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from file if it exists."""
        if os.path.exists(self.config_path):
            self.config = RetrievalSystemConfig.load(self.config_path)

    def save(self) -> None:
        """Save current configuration to file."""
        self.config.save(self.config_path)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-notation key.

        Args:
            key: Configuration key (e.g., 'chunking.chunk_size')
            default: Default value if key not found

        Returns:
            Configuration value
        """
        parts = key.split(".")
        value: Any = self.config

        for part in parts:
            if isinstance(value, dict):
                value = value.get(part, default)
            elif hasattr(value, part):
                value = getattr(value, part)
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> bool:
        """
        Set configuration value by dot-notation key.

        Args:
            key: Configuration key (e.g., 'chunking.chunk_size')
            value: Value to set

        Returns:
            bool: True if value was set successfully
        """
        parts = key.split(".")

        if len(parts) == 1:
            # Top-level key
            if hasattr(self.config, parts[0]):
                setattr(self.config, parts[0], value)
                return True
            return False

        # Navigate to parent
        parent: Any = self.config
        for part in parts[:-1]:
            if hasattr(parent, part):
                parent = getattr(parent, part)
            else:
                return False

        # Set value
        if hasattr(parent, parts[-1]):
            setattr(parent, parts[-1], value)
            return True
        return False

    def update(self, updates: Dict[str, Any]) -> None:
        """
        Update multiple configuration values.

        Args:
            updates: Dictionary of key-value pairs to update
        """
        for key, value in updates.items():
            self.set(key, value)

    def reset_to_defaults(self) -> None:
        """Reset configuration to default values."""
        self.config = RetrievalSystemConfig()

    def to_dict(self) -> Dict[str, Any]:
        """Get current configuration as dictionary."""
        return self.config.to_dict()

    def validate(self) -> bool:
        """Validate current configuration."""
        return self.config.validate()


# Global configuration instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_path: Optional[str] = None) -> ConfigManager:
    """
    Get or create global configuration manager.

    Args:
        config_path: Optional custom config path

    Returns:
        ConfigManager instance
    """
    global _config_manager

    if _config_manager is None:
        _config_manager = ConfigManager(config_path)

    return _config_manager


def get_config() -> RetrievalSystemConfig:
    """
    Get current retrieval system configuration.

    Returns:
        RetrievalSystemConfig instance
    """
    return get_config_manager().config
