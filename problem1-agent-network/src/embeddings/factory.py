"""Factory for creating and calibrating embedding providers."""


from src.config import EmbedderBackend, settings
from src.embeddings.base import BaseEmbedder
from src.embeddings.mock_embedder import MockEmbedder
from src.embeddings.openai_embedder import OpenAIEmbedder
from src.embeddings.sentence_transformers_embedder import (
    HAVE_SENTENCE_TRANSFORMERS,
    SentenceTransformersEmbedder,
)

_embedder_cache: dict[str, BaseEmbedder] = {}


def get_embedder(force_type: EmbedderBackend | None = None) -> BaseEmbedder:
    """Returns a cached singleton or calibrated embedder instance."""
    chosen_type = force_type or settings.embedder_type
    key = str(chosen_type)
    if key in _embedder_cache:
        return _embedder_cache[key]

    instance: BaseEmbedder
    if chosen_type == EmbedderBackend.SENTENCE_TRANSFORMERS and HAVE_SENTENCE_TRANSFORMERS:
        try:
            instance = SentenceTransformersEmbedder(model_name=settings.sentence_model_name)
        except Exception:
            instance = MockEmbedder()

    elif chosen_type == EmbedderBackend.OPENAI and settings.openai_api_key:
        instance = OpenAIEmbedder(
            api_key=settings.openai_api_key,
            model_name=settings.openai_model_name,
        )
    else:
        instance = MockEmbedder()

    _embedder_cache[key] = instance
    return instance
