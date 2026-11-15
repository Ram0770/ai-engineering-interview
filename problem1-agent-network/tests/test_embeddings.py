"""Test pluggable embedding backends and threshold calibration."""


from src.config import EmbedderBackend
from src.embeddings.factory import get_embedder
from src.embeddings.mock_embedder import MockEmbedder
from src.embeddings.sentence_transformers_embedder import (
    HAVE_SENTENCE_TRANSFORMERS,
    SentenceTransformersEmbedder,
)


def test_pluggable_embedders_and_calibration() -> None:
    """Verifies that embedder factory supplies calibrated embedding providers."""
    # 1. Deterministic Mock Embedder
    mock_emb = get_embedder(force_type=EmbedderBackend.MOCK)
    assert isinstance(mock_emb, MockEmbedder)
    vec1 = mock_emb.embed_text("Test query text")
    vec2 = mock_emb.embed_text("Test query text")
    assert vec1 == vec2
    assert len(vec1) == 128

    # 2. Real Sentence-Transformers Embedder
    if HAVE_SENTENCE_TRANSFORMERS:
        st_emb = get_embedder(force_type=EmbedderBackend.SENTENCE_TRANSFORMERS)
        assert isinstance(st_emb, SentenceTransformersEmbedder)
        real_vec = st_emb.embed_text("Test sentence transformers embedding")
        assert len(real_vec) == 384
        assert isinstance(real_vec[0], float)
