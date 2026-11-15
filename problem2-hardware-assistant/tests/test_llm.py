"""Unit tests for LLM abstraction layer."""

from src.llm.base import ChatMessage, ChatResponse
from src.llm.mock_client import MockLLMClient
from src.llm.ollama_client import OllamaClient


def test_mock_llm_deterministic_responses() -> None:
    client = MockLLMClient(
        scripted_responses=[
            ChatResponse(content="Preprogrammed mock answer")
        ]
    )
    res = client.generate_response([ChatMessage(role="user", content="hello")])
    assert res.content == "Preprogrammed mock answer"


def test_ollama_client_payload_formatting() -> None:
    client = OllamaClient(base_url="http://localhost:11434", model="llama3.2:3b")
    # Verify client attributes
    assert client.base_url == "http://localhost:11434"
    assert client.model == "llama3.2:3b"

    # Verify connection error handling when Ollama is offline
    msgs = [ChatMessage(role="user", content="Ping")]
    res = client.generate_response(msgs)
    assert res.finish_reason == "error"
    assert "Could not connect to Ollama" in (res.content or "")
