"""CLI tests for Typer commands, privacy flags, and cloud warnings."""

from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()


def test_cli_privacy_command() -> None:
    """Verifies that 'hw-assistant privacy' prints the privacy policy and egress notes."""
    result = runner.invoke(app, ["privacy"])
    assert result.exit_code == 0
    assert "Data Privacy & Network Egress Policy" in result.output
    assert "Ollama" in result.output
    assert "audit.log" in result.output


def test_cli_chat_exit() -> None:
    """Verifies that entering 'exit' cleanly terminates the chat session."""
    result = runner.invoke(app, ["chat", "--backend", "mock"], input="exit\n")
    assert result.exit_code == 0
    assert "Goodbye!" in result.output


def test_privacy_flag_and_cloud_warning() -> None:
    """Verifies that selecting a cloud backend produces a yellow warning banner."""
    # Note: openai requires API key so it will fail initialization or warn
    result = runner.invoke(app, ["chat", "--backend", "openai", "--all-tools"], input="exit\n")
    assert "WARNING: Cloud LLM backend 'openai' is active" in result.output
