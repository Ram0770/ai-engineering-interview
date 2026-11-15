"""Interactive CLI chat interface built with Typer and Rich."""

import os

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from src.config import LLMBackend, settings
from src.discovery import get_capabilities
from src.execution.engine import SafeExecutionEngine
from src.llm.base import LLMClient
from src.llm.cloud_client import AnthropicClient, OpenAIClient
from src.llm.mock_client import MockLLMClient
from src.llm.ollama_client import OllamaClient
from src.orchestrator import HardwareOrchestrator
from src.tools.registry import ToolRegistry

app = typer.Typer(
    name="hw-assistant",
    help="Local Linux Hardware Q&A Assistant with safe deterministic tool calling.",
    add_completion=False,
)
console = Console()

PRIVACY_DOCUMENTATION = """# Data Privacy & Network Egress Policy

### 1. Default On-Device Operation
By default, the Linux Hardware Q&A Assistant runs **100% offline and locally**:
- **Local Model Engine**: Uses **Ollama** running on `http://localhost:11434`.
- **Zero Internet Telemetry**: No system information, hardware specifications, CPU models, disk serials, or conversation logs are transmitted across the network.
- **Local Audit Log**: All tool executions are logged locally to `audit.log` with sensitive identifiers (MAC addresses, UUIDs, serial numbers) redacted by default.

### 2. Cloud LLM Backends (Optional)
If you explicitly configure a cloud backend (`--backend openai` or `--backend anthropic`):
- **Egress Warning**: Hardware inspection data (including CPU model, RAM topology, storage layout, GPU specs) **WILL BE TRANSMITTED** over HTTPS to third-party model APIs.
- **Security Recommendation**: For enterprise and privacy-sensitive hosts, always use `--backend ollama` or `--backend mock`.
"""


def check_root_privilege() -> None:
    """Refuses or warns if the entire application is executed as root (EUID 0)."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        console.print(
            Panel(
                "[bold red]SECURITY WARNING: Running as root (EUID 0) is strongly discouraged![/bold red]\n"
                "The assistant is engineered to run as an unprivileged user, using scoped sudoers "
                "only for commands that strictly require elevated privileges (e.g. dmidecode).\n"
                "Please run as a standard user: [bold green]hw-assistant chat[/bold green]",
                title="Privilege Escalation Warning",
                border_style="red",
            )
        )


def build_llm_client(backend: LLMBackend, model: str | None = None) -> LLMClient:
    """Instantiates the requested LLM client backend."""
    if backend == LLMBackend.OLLAMA:
        return OllamaClient(model=model or settings.ollama_model)
    elif backend == LLMBackend.OPENAI:
        return OpenAIClient(model=model or settings.openai_model)
    elif backend == LLMBackend.ANTHROPIC:
        return AnthropicClient(model=model or settings.anthropic_model)
    elif backend == LLMBackend.MOCK:
        return MockLLMClient()
    raise ValueError(f"Unsupported backend: {backend}")


@app.command()
def privacy() -> None:
    """Displays the hardware data privacy and network egress documentation."""
    console.print(Markdown(PRIVACY_DOCUMENTATION))


@app.command()
def ask(
    query: str = typer.Argument(..., help="The hardware question to ask"),
    backend: LLMBackend = typer.Option(
        settings.backend,
        "--backend",
        "-b",
        help="LLM backend: ollama (local), openai, anthropic, or mock (offline)",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        "-m",
        help="Model identifier (e.g. llama3.2:3b, gpt-4o-mini)",
    ),
    all_tools: bool = typer.Option(
        True,
        "--all-tools",
        help="Register all tools including mock fallbacks",
    ),
) -> None:
    """Answers a single hardware question non-interactively."""
    check_root_privilege()
    caps = get_capabilities()
    engine = SafeExecutionEngine(capabilities=caps)
    registry = ToolRegistry(engine, include_all=all_tools)
    llm = build_llm_client(backend, model=model)
    orchestrator = HardwareOrchestrator(
        llm_client=llm,
        execution_engine=engine,
        tool_registry=registry,
    )

    answer, _ = orchestrator.handle_user_query(query)
    console.print(Markdown(answer))


@app.command()
def chat(
    backend: LLMBackend = typer.Option(
        settings.backend,
        "--backend",
        "-b",
        help="LLM backend: ollama (local), openai, anthropic, or mock (offline)",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        "-m",
        help="Model identifier (e.g. llama3.2:3b, gpt-4o-mini)",
    ),
    all_tools: bool = typer.Option(
        False,
        "--all-tools",
        help="Force registration of all tools regardless of discovery capabilities",
    ),
) -> None:
    """Starts an interactive multi-turn hardware Q&A session."""
    check_root_privilege()

    # Cloud Egress Warning
    if backend in (LLMBackend.OPENAI, LLMBackend.ANTHROPIC):
        console.print(
            Panel(
                f"[bold yellow]WARNING: Cloud LLM backend '{backend.value}' is active.[/bold yellow]\n"
                "System hardware specifications will be transmitted over the internet to remote APIs.\n"
                "Run with [bold green]--privacy[/bold green] for details or use [bold green]--backend ollama[/bold green] for complete privacy.",
                border_style="yellow",
            )
        )

    # Initialize components
    caps = get_capabilities()
    engine = SafeExecutionEngine(capabilities=caps)
    registry = ToolRegistry(engine, include_all=all_tools)
    llm = build_llm_client(backend, model=model)
    orchestrator = HardwareOrchestrator(
        llm_client=llm,
        execution_engine=engine,
        tool_registry=registry,
    )

    console.print(
        Panel(
            f"[bold cyan]Linux Hardware Q&A Assistant[/bold cyan]\n"
            f"Backend: [green]{backend.value}[/green] | Host OS: [yellow]{caps.os_type}[/yellow] | "
            f"Active Tools: [magenta]{len(registry.registered_tool_names)}[/magenta]\n"
            f"Type [bold]exit[/bold] or [bold]quit[/bold] to exit.",
            border_style="cyan",
        )
    )

    while True:
        try:
            query = Prompt.ask("\n[bold cyan]User[/bold cyan]").strip()
            if not query:
                continue
            if query.lower() in ("exit", "quit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break

            with console.status("[bold green]Inspecting hardware and synthesizing verified answer...[/bold green]"):
                answer, tool_results = orchestrator.handle_user_query(query)

            console.print("\n[bold green]Assistant[/bold green]:")
            console.print(Markdown(answer))

        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session ended.[/dim]")
            break
        except Exception as e:
            console.print(f"[bold red]Error[/bold red]: {e}")


def main() -> None:
    """Entry point for hw-assistant CLI."""
    app()


if __name__ == "__main__":
    main()
