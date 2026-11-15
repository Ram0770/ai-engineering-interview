"""Real sentence-transformers embedder using all-MiniLM-L6-v2."""


from src.embeddings.base import BaseEmbedder

try:
    from sentence_transformers import SentenceTransformer
    HAVE_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAVE_SENTENCE_TRANSFORMERS = False


class SentenceTransformersEmbedder(BaseEmbedder):
    """Dense vector embedder powered by local sentence-transformers models."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        if not HAVE_SENTENCE_TRANSFORMERS:
            raise ImportError(
                "sentence-transformers is not installed. Install via 'pip install sentence-transformers'."
            )
        self.model_name = model_name
        self._model: SentenceTransformer | None = None
        self.dimension = 384
        # MiniLM cosine similarities cluster around 0.45 - 0.70 for related commercial texts
        self.default_threshold = 0.45

    @property
    def model(self) -> "SentenceTransformer":
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_text(self, text: str) -> list[float]:
        embedding = self.model.encode(text, normalize_embeddings=True)
        return [float(x) for x in embedding]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return [[float(x) for x in row] for row in embeddings]
