"""Abstract embedding model interface."""

from abc import ABC, abstractmethod


class BaseEmbedder(ABC):
    """Abstract protocol for text embedding providers."""

    dimension: int
    default_threshold: float = 0.75

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Embeds a single text string into a normalized dense vector."""
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embeds multiple text strings in batch for efficiency."""
        pass
