"""Test routing evaluation runner with real embedder and ground truth dataset."""

from pathlib import Path

import pytest

from eval.eval_routing import evaluate_dataset


@pytest.mark.asyncio
async def test_routing_precision_recall_real_embedder() -> None:
    """Evaluates multi-stage relevance routing against 25 ground-truth cases."""
    dataset_path = Path(__file__).resolve().parent.parent / "eval" / "routing_ground_truth.json"
    assert dataset_path.exists(), f"Ground truth dataset missing at {dataset_path}"

    summary = await evaluate_dataset(
        dataset_path=dataset_path,
        embedder_type="sentence-transformers",
        calibrated_threshold=0.68,
    )

    assert summary["total_cases"] == 25
    assert summary["f1"] >= 0.85, f"F1 score {summary['f1']} below 0.85 bar"
    assert summary["precision"] >= 0.85, f"Precision {summary['precision']} below 0.85 bar"
    assert summary["recall"] >= 0.85, f"Recall {summary['recall']} below 0.85 bar"
