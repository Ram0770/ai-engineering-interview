"""Tests for the 20+ cases evaluation suite runner."""

from eval.eval_suite import run_eval


def test_evaluation_benchmark_20_cases() -> None:
    """Verifies that running the evaluation suite against mock fixtures yields 100% pass rate."""
    summary = run_eval(backend="mock")
    assert summary["total"] >= 20
    assert summary["passed"] == summary["total"]
    assert summary["pass_rate_percent"] == 100.0

