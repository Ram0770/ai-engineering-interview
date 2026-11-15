"""OpenAI text-embedding API adapter."""

import httpx

from src.embeddings.base import BaseEmbedder


class OpenAIEmbedder(BaseEmbedder):
    """Cloud embedding provider using OpenAI text-embedding-3-small."""

    def __init__(self, api_key: str, model_name: str = "text-embedding-3-small") -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.dimension = 1536
        self.default_threshold = 0.70

    def embed_text(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        url = "https://api.openai.com/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "input": texts,
        }
        with httpx.Client(timeout=30.0) as client:
            res = client.post(url, headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()

        return [item["embedding"] for item in data["data"]]
