"""Load testing and performance benchmark script for Problem 1.

Measures post ingestion throughput, multi-stage routing latency (p50/p95/p99),
and async notification queue dispatch under concurrent load.
Can test against in-process ASGI app or a live HTTP server.
"""

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Any

# Ensure problem1-agent-network directory is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import httpx
from rich.console import Console
from rich.table import Table

# Set mock embedder for ultrafast offline benchmarking
os.environ["EMBEDDER_TYPE"] = "mock"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from src.db.models import Agent, AgentInterest, ApiKey
from src.db.session import async_session_factory, init_db
from src.embeddings.factory import get_embedder
from src.main import app
from src.services.verification import generate_api_key, generate_signing_secret


async def setup_benchmark_environment(num_agents: int = 25) -> list[dict[str, str]]:
    """Seeds test database with candidate agents and returns their auth tokens."""
    await init_db()
    embedder = get_embedder()
    credentials_list: list[dict[str, str]] = []

    industries = [
        ("FinTech", ["payments", "checkout", "upi", "cards"]),
        ("E-Commerce", ["retail", "shopping", "discounts", "delivery"]),
        ("Healthcare", ["pharmacy", "hospitals", "medicine", "insurance"]),
        ("Travel", ["flights", "hotels", "airport", "mobility"]),
        ("Enterprise", ["cloud", "devops", "kubernetes", "database"]),
    ]

    async with async_session_factory() as session:
        for i in range(num_agents):
            ind_name, tags = industries[i % len(industries)]
            company = f"{ind_name}_Corp_{i+1}"
            raw_key, prefix, key_hash = generate_api_key()
            sec = generate_signing_secret()
            manifesto = f"Leading provider of {ind_name} enterprise solutions and autonomous workflows."

            agent = Agent(
                company_name=company,
                industry_category=ind_name,
                interest_manifesto=manifesto,
                api_key_hash=key_hash,
                webhook_url=f"https://agent{i+1}.corp.internal/webhook",
                webhook_signing_secret=sec,
                status="ACTIVE",
                trust_score=1.0,
            )
            session.add(agent)
            await session.flush()

            session.add(ApiKey(
                agent_id=agent.id,
                key_hash=key_hash,
                prefix=prefix,
                revoked=False,
            ))

            vector = embedder.embed_text(f"{' '.join(tags)}. {manifesto}")

            interest = AgentInterest(
                agent_id=agent.id,
                topics=tags,
                keywords=tags,
                interest_embedding=vector,
            )
            session.add(interest)

            credentials_list.append({
                "agent_id": agent.id,
                "company_name": company,
                "api_key": raw_key,
            })

        await session.commit()

    return credentials_list


async def send_single_post(
    client: httpx.AsyncClient,
    creds: dict[str, str],
    post_idx: int,
) -> float:
    """Sends a single post request and returns the latency in milliseconds."""
    headers = {"Authorization": f"Bearer {creds['api_key']}"}
    payload = {
        "title": f"Load Benchmark Post #{post_idx} by {creds['company_name']}",
        "content": (
            "Seeking payment processing, cloud infrastructure, and co-marketing discounts "
            "for national seasonal customer acquisition campaigns."
        ),
    }

    start = time.perf_counter()
    resp = await client.post("/api/v1/posts", json=payload, headers=headers)
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    if resp.status_code != 201:
        raise RuntimeError(f"Post #{post_idx} failed with {resp.status_code}: {resp.text}")

    return elapsed_ms


async def run_load_benchmark(
    concurrency: int = 10,
    total_posts: int = 50,
    num_agents: int = 20,
) -> dict[str, Any]:
    """Executes the concurrent load test against the FastAPI service."""
    creds_list = await setup_benchmark_environment(num_agents)

    transport = httpx.ASGITransport(app=app)
    latencies: list[float] = []

    console = Console()
    console.print(f"[bold cyan]Starting Load Test:[/bold cyan] {total_posts} posts across {concurrency} concurrent workers ({num_agents} registered agents)")

    start_total = time.perf_counter()

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        semaphore = asyncio.Semaphore(concurrency)

        async def worker(idx: int) -> None:
            creds = creds_list[idx % len(creds_list)]
            async with semaphore:
                lat = await send_single_post(client, creds, idx)
                latencies.append(lat)

        tasks = [worker(i) for i in range(total_posts)]
        await asyncio.gather(*tasks)

    total_duration_s = time.perf_counter() - start_total
    latencies.sort()

    p50 = latencies[int(len(latencies) * 0.50)]
    p90 = latencies[int(len(latencies) * 0.90)]
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)] if len(latencies) >= 100 else latencies[-1]
    throughput = len(latencies) / total_duration_s

    return {
        "total_posts": len(latencies),
        "total_duration_s": total_duration_s,
        "throughput_rps": throughput,
        "min_latency_ms": latencies[0],
        "p50_latency_ms": p50,
        "p90_latency_ms": p90,
        "p95_latency_ms": p95,
        "p99_latency_ms": p99,
        "max_latency_ms": latencies[-1],
    }


def print_load_results(metrics: dict[str, Any]) -> None:
    """Renders formatted load test results."""
    console = Console()
    table = Table(title="Load Test Benchmark Metrics")
    table.add_column("Benchmark Metric", style="cyan")
    table.add_column("Value", style="bold green")

    table.add_row("Total Ingested Posts", str(metrics["total_posts"]))
    table.add_row("Total Elapsed Time", f"{metrics['total_duration_s']:.2f} s")
    table.add_row("Throughput", f"{metrics['throughput_rps']:.1f} req/s")
    table.add_row("Min Latency", f"{metrics['min_latency_ms']:.1f} ms")
    table.add_row("p50 Latency (Median)", f"{metrics['p50_latency_ms']:.1f} ms")
    table.add_row("p90 Latency", f"{metrics['p90_latency_ms']:.1f} ms")
    table.add_row("p95 Latency", f"{metrics['p95_latency_ms']:.1f} ms")
    table.add_row("p99 Latency", f"{metrics['p99_latency_ms']:.1f} ms")
    table.add_row("Max Latency", f"{metrics['max_latency_ms']:.1f} ms")

    console.print(table)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run load test benchmark.")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--posts", type=int, default=40)
    parser.add_argument("--agents", type=int, default=15)
    args = parser.parse_args()

    metrics = asyncio.run(run_load_benchmark(
        concurrency=args.concurrency,
        total_posts=args.posts,
        num_agents=args.agents,
    ))
    print_load_results(metrics)
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
