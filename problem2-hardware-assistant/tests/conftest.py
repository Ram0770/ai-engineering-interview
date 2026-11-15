"""Pytest fixtures and configuration for Problem 2."""

from pathlib import Path

import pytest

from eval.eval_suite import FixtureMockEngine
from src.tools.registry import ToolRegistry


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "synthetic" / "ubuntu_2204"


@pytest.fixture
def mock_engine(fixtures_dir: Path) -> FixtureMockEngine:
    return FixtureMockEngine(fixtures_dir)


@pytest.fixture
def tool_registry(mock_engine: FixtureMockEngine) -> ToolRegistry:
    return ToolRegistry(mock_engine, include_all=True)
