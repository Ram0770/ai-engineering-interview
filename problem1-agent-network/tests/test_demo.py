"""Test interactive demo script execution."""

import subprocess
import sys
from pathlib import Path


def test_demo_script_execution() -> None:
    """Verifies that demo.py executes cleanly as an independent CLI demonstration."""
    demo_script = Path(__file__).resolve().parent.parent / "demo.py"
    assert demo_script.exists()

    result = subprocess.run(
        [sys.executable, str(demo_script)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Demo failed with error:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert "Demonstration Completed Successfully!" in result.stdout
