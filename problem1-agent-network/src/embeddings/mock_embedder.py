"""Deterministic mock embedder for offline testing and fast CI runs."""

import hashlib
import math

from src.embeddings.base import BaseEmbedder

# Semantic clusters for deterministic similarity tests
SEMANTIC_CLUSTERS = {
    "food_dining": ["swiggy", "food", "delivery", "zomato", "restaurant", "order", "feast", "diwali"],
    "payments_fintech": ["phonepe", "upi", "cashback", "payment", "wallet", "merchant", "paytm", "discount"],
    "banking_cards": ["hdfc", "card", "bank", "credit", "debit", "emi", "interest", "loan"],
    "automotive": ["bajaj", "auto", "bike", "motorcycle", "vehicle", "scooter", "engine"],
    "ecommerce": ["flipkart", "amazon", "shopping", "festive", "sale", "deals"],
}


class MockEmbedder(BaseEmbedder):
    """Deterministic, dimension-configurable mock embedding generator."""

    def __init__(self, dimension: int = 128) -> None:
        self.dimension = dimension
        self.default_threshold = 0.50

    def embed_text(self, text: str) -> list[float]:
        vec = [0.0] * self.dimension
        lower_text = text.lower()

        # Add semantic cluster energy
        for idx, (_cluster_name, keywords) in enumerate(SEMANTIC_CLUSTERS.items()):
            dim_offset = (idx * 20) % self.dimension
            for kw in keywords:
                if kw in lower_text:
                    for i in range(15):
                        vec[(dim_offset + i) % self.dimension] += 1.0

        # Deterministic token hashing for residual fine-grained variance
        words = lower_text.split()
        for w in words:
            h = int(hashlib.sha256(w.encode("utf-8")).hexdigest(), 16)
            pos = h % self.dimension
            vec[pos] += 0.2

        # L2 normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            return [round(x / norm, 6) for x in vec]
        # Return fallback unit vector if zero
        fallback = [0.0] * self.dimension
        fallback[0] = 1.0
        return fallback

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(t) for t in texts]
