"""Evaluation runner for multi-stage relevance routing.

Evaluates precision, recall, and F1 against ground truth business cases.
Supports real sentence-transformers model ('all-MiniLM-L6-v2') and mock embedder.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

# Ensure problem1-agent-network directory is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["AGENT_NET_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import torch

torch.set_num_threads(1)

from rich.console import Console
from rich.table import Table

from src.db.models import Agent, AgentInterest, Post
from src.db.session import async_session_factory, init_db
from src.embeddings.factory import get_embedder
from src.routing.pipeline import RoutingPipeline


async def evaluate_dataset(
    dataset_path: Path,
    embedder_type: str = "sentence-transformers",
    calibrated_threshold: float = 0.70,
) -> dict[str, Any]:
    """Runs routing evaluation against ground truth dataset."""
    os.environ["EMBEDDER_TYPE"] = embedder_type
    os.environ["AGENT_NET_EMBEDDER_TYPE"] = embedder_type
    os.environ["ROUTING_SIMILARITY_THRESHOLD"] = str(calibrated_threshold)
    os.environ["AGENT_NET_SIMILARITY_THRESHOLD"] = str(calibrated_threshold)

    # Initialize in-memory / test SQLite DB
    await init_db()

    with open(dataset_path, encoding="utf-8") as f:
        cases = json.load(f)

    from src.config import EmbedderBackend
    embedder = get_embedder(force_type=EmbedderBackend(embedder_type))
    pipeline = RoutingPipeline(threshold=calibrated_threshold, top_k=100)

    tp, fp, tn, fn = 0, 0, 0, 0
    results: list[dict[str, Any]] = []

    async with async_session_factory() as session:
        for idx, case in enumerate(cases):
            case_id = case.get("case_id", f"case-{idx+1}")
            domain = case.get("domain", "general")
            post_data = case["post"]
            candidate_data = case["candidate"]
            expected = case["expected_decision"]

            # 1. Create Author Agent
            author = Agent(
                company_name=post_data["author_company"],
                industry_category=domain,
                webhook_url=f"https://{post_data['author_company'].lower().replace(' ', '')}.com/webhook",
                interest_manifesto=post_data["title"],
                api_key_hash=f"hash_{idx}",
                webhook_signing_secret="sec_test",
                status="ACTIVE",
                trust_score=0.9,
            )
            session.add(author)
            await session.flush()

            # 2. Create Candidate Agent
            candidate_agent = Agent(
                company_name=candidate_data["company_name"],
                industry_category=domain,
                webhook_url=f"https://{candidate_data['company_name'].lower().replace(' ', '')}.com/webhook",
                interest_manifesto=candidate_data["manifesto"],
                api_key_hash=f"hash_cand_{idx}",
                webhook_signing_secret="sec_cand",
                status="ACTIVE",
                trust_score=0.9,
            )
            session.add(candidate_agent)
            await session.flush()

            # 3. Create Candidate Agent Interest
            cand_manifesto = candidate_data["manifesto"]
            cand_tags = candidate_data["tags"]
            cand_text = f"{' '.join(cand_tags)}. {cand_manifesto}"
            cand_vector = embedder.embed_text(cand_text)

            interest = AgentInterest(
                agent_id=candidate_agent.id,
                topics=cand_tags,
                keywords=cand_tags,
                interest_embedding=cand_vector,
            )
            session.add(interest)
            await session.flush()

            # 4. Create Post
            post_text = f"{post_data['title']}. {post_data['content']}"
            post_vector = embedder.embed_text(post_text)
            post = Post(
                author_agent_id=author.id,
                title=post_data["title"],
                content=post_data["content"],
                post_embedding=post_vector,
            )
            session.add(post)
            await session.flush()

            # 5. Route Post
            decisions = await pipeline.route_post(session, post)

            # Find decision for our candidate
            cand_decision = next(
                (d for d in decisions if d.candidate.candidate.agent.id == candidate_agent.id),
                None,
            )

            actual = cand_decision.decision if cand_decision else "DROPPED"
            score = cand_decision.final_score if cand_decision else 0.0
            reason = cand_decision.reason if cand_decision else "Filtered at Stage 1 / Stage 2"

            is_match = (actual == expected)
            if expected == "NOTIFIED" and actual == "NOTIFIED":
                tp += 1
            elif expected == "DROPPED" and actual == "NOTIFIED":
                fp += 1
            elif expected == "DROPPED" and actual == "DROPPED":
                tn += 1
            elif expected == "NOTIFIED" and actual == "DROPPED":
                fn += 1

            results.append({
                "case_id": case_id,
                "domain": domain,
                "author": post_data["author_company"],
                "candidate": candidate_data["company_name"],
                "expected": expected,
                "actual": actual,
                "match": is_match,
                "score": score,
                "reason": reason,
            })

    # Compute classification metrics
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / len(cases) if len(cases) > 0 else 0.0

    return {
        "embedder": embedder_type,
        "calibrated_threshold": calibrated_threshold,
        "total_cases": len(cases),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": accuracy,
        "results": results,
    }


def print_evaluation_report(eval_summary: dict[str, Any]) -> None:
    """Renders formatted evaluation results using Rich."""
    console = Console()

    console.print(f"\n[bold cyan]Routing Evaluation Benchmark[/bold cyan] (Embedder: [bold yellow]{eval_summary['embedder']}[/bold yellow], Calibrated Threshold: {eval_summary['calibrated_threshold']})")

    table = Table(title="Evaluation Test Cases")
    table.add_column("Case ID", style="dim", width=9)
    table.add_column("Author", width=14)
    table.add_column("Candidate", width=16)
    table.add_column("Expected", width=10)
    table.add_column("Actual", width=10)
    table.add_column("Status", width=8)
    table.add_column("Score", justify="right", width=7)
    table.add_column("Decision Rationale", width=36)

    for r in eval_summary["results"]:
        status_style = "[bold green]PASS[/bold green]" if r["match"] else "[bold red]FAIL[/bold red]"
        actual_style = "[green]NOTIFIED[/green]" if r["actual"] == "NOTIFIED" else "[yellow]DROPPED[/yellow]"
        table.add_row(
            r["case_id"],
            r["author"],
            r["candidate"],
            r["expected"],
            actual_style,
            status_style,
            f"{r['score']:.3f}",
            r["reason"][:35] + "..." if len(r["reason"]) > 35 else r["reason"],
        )

    console.print(table)

    summary_table = Table(title="Performance Summary")
    summary_table.add_column("Metric", style="bold cyan")
    summary_table.add_column("Value", style="bold")

    summary_table.add_row("Total Test Cases", str(eval_summary["total_cases"]))
    summary_table.add_row("True Positives (TP)", str(eval_summary["tp"]))
    summary_table.add_row("True Negatives (TN)", str(eval_summary["tn"]))
    summary_table.add_row("False Positives (FP)", str(eval_summary["fp"]))
    summary_table.add_row("False Negatives (FN)", str(eval_summary["fn"]))
    summary_table.add_row("Precision", f"{eval_summary['precision']:.2%}")
    summary_table.add_row("Recall", f"{eval_summary['recall']:.2%}")
    summary_table.add_row("F1-Score", f"{eval_summary['f1']:.2%}")
    summary_table.add_row("Accuracy", f"{eval_summary['accuracy']:.2%}")

    console.print(summary_table)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate relevance routing precision and recall.")
    parser.add_argument("--dataset", type=str, default=str(BASE_DIR / "eval" / "routing_ground_truth.json"))
    parser.add_argument("--embedder", type=str, default="sentence-transformers", choices=["sentence-transformers", "mock", "openai"])
    parser.add_argument("--threshold", type=float, default=0.68)
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Dataset not found at {dataset_path}")
        sys.exit(1)

    eval_summary = asyncio.run(evaluate_dataset(
        dataset_path=dataset_path,
        embedder_type=args.embedder,
        calibrated_threshold=args.threshold,
    ))

    print_evaluation_report(eval_summary)

    # Require minimum F1 score of 80% to pass
    if eval_summary["f1"] < 0.80:
        print(f"\n[FAIL] F1 score {eval_summary['f1']:.2%} is below 80% threshold.")
        sys.exit(1)
    else:
        print(f"\n[SUCCESS] Routing benchmark passed with F1 score {eval_summary['f1']:.2%}")
        sys.exit(0)


if __name__ == "__main__":
    main()
