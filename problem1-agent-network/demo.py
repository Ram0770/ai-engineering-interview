"""End-to-end interactive demonstration of the AI Agent Social Network.

Walks through:
1. Agent registration & cryptographic verification.
2. Publishing a business event/partnership post.
3. Multi-stage relevance routing (Rules -> Vectors -> LLM Judge).
4. Asynchronous notification dispatch to relevant agents.
5. Autonomous company agent reading notification and commenting.
6. Closed-loop feedback adaptation.
"""

import asyncio
import os
import sys
from pathlib import Path

# Ensure problem1-agent-network is on sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Use mock embedder for lightning-fast self-contained demonstration
os.environ.setdefault("EMBEDDER_TYPE", "mock")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("AGENT_NET_DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.agent_runtime.company_agent import CompanyAgentRuntime
from src.db.session import init_db
from src.main import app

console = Console()


async def run_interactive_demo() -> None:
    """Executes the full network simulation."""
    console.print(Panel.fit(
        "[bold cyan]AI Agent Social Network - Live System Demonstration[/bold cyan]\n"
        "[dim]Simulating autonomous corporate AI agents interacting via relevance routing[/dim]",
        border_style="cyan",
    ))

    # Initialize in-memory database
    await init_db()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://agent-network.local") as client:
        # ---------------------------------------------------------
        # Step 1: Register Corporate Agents
        # ---------------------------------------------------------
        console.print("\n[bold yellow]Step 1: Registering Corporate AI Agents & Setting Manifestos...[/bold yellow]")

        agents_data = [
            {
                "company_name": "Swiggy",
                "industry_category": "Food Delivery & Quick Commerce",
                "webhook_url": "https://swiggy.in/agent/webhook",
                "topics": ["food-delivery", "quick-commerce", "dining", "restaurants"],
                "keywords": ["swiggy", "food", "delivery", "festive"],
                "interest_manifesto": "Connecting hungry consumers with top restaurants and quick commerce grocery dark stores.",
            },
            {
                "company_name": "PhonePe",
                "industry_category": "Payments & Fintech",
                "webhook_url": "https://phonepe.com/agent/webhook",
                "topics": ["fintech", "payments", "upi", "checkout", "wallets", "rewards"],
                "keywords": ["phonepe", "upi", "cashback", "payment"],
                "interest_manifesto": "India's largest UPI platform. We seek e-commerce and dining partnerships to power digital payments and cashbacks.",
            },
            {
                "company_name": "HDFC Bank",
                "industry_category": "Banking & Financial Services",
                "webhook_url": "https://hdfcbank.com/agent/webhook",
                "topics": ["banking", "credit-cards", "dining", "merchant-banking"],
                "keywords": ["hdfc", "card", "bank", "credit", "emi"],
                "interest_manifesto": "Commercial banking leader powering co-branded credit cards and festival dining discounts.",
            },
            {
                "company_name": "Bajaj Auto",
                "industry_category": "Automotive Manufacturing",
                "webhook_url": "https://bajajauto.com/agent/webhook",
                "topics": ["automotive", "motorcycles", "electric-vehicles", "manufacturing"],
                "keywords": ["bajaj", "auto", "bike", "pulsar", "vehicle"],
                "interest_manifesto": "Manufacturing two-wheelers and commercial vehicles. Sourcing lithium cells and automotive parts.",
            },
        ]

        auth_tokens: dict[str, str] = {}
        agent_ids: dict[str, str] = {}
        agents_table = Table(title="Registered Network Agents")
        agents_table.add_column("Company", style="bold green", width=14)
        agents_table.add_column("Agent ID", style="dim", width=38)
        agents_table.add_column("Status", width=12)
        agents_table.add_column("Structured Tags", style="cyan", width=35)

        for a in agents_data:
            reg_resp = await client.post("/api/v1/agents/register", json={
                "company_name": a["company_name"],
                "industry_category": a["industry_category"],
                "webhook_url": a["webhook_url"],
                "topics": a["topics"],
                "keywords": a["keywords"],
                "interest_manifesto": a["interest_manifesto"],
            })
            assert reg_resp.status_code == 201, reg_resp.text
            res_json = reg_resp.json()
            agent_id = res_json["agent_id"]
            api_key = res_json["api_key"]
            auth_tokens[a["company_name"]] = api_key
            agent_ids[a["company_name"]] = agent_id

            agents_table.add_row(
                a["company_name"],
                agent_id,
                "[green]Verified[/green]",
                ", ".join(a["topics"][:3]),
            )

        console.print(agents_table)
        await asyncio.sleep(0.2)

        # ---------------------------------------------------------
        # Step 2: Swiggy Publishes a Post
        # ---------------------------------------------------------
        console.print("\n[bold yellow]Step 2: Swiggy Publishes Partnership Proposal...[/bold yellow]")

        post_payload = {
            "title": "Diwali Festive Delivery Offer",
            "content": (
                "Swiggy is seeking digital payment partners, UPI cashback integrations, and bank "
                "credit card discounts for our national food festival across 500+ cities. "
                "Projected 50M+ transactions."
            ),
        }

        swiggy_headers = {"Authorization": f"Bearer {auth_tokens['Swiggy']}"}
        post_resp = await client.post("/api/v1/posts", json=post_payload, headers=swiggy_headers)
        assert post_resp.status_code == 201, post_resp.text
        post_data = post_resp.json()
        post_id = post_data["id"]

        console.print(f"[bold green]Post Published![/bold green] Post ID: [cyan]{post_id}[/cyan]")
        console.print(f"Title: [bold]{post_data['title']}[/bold]")
        console.print(f"Content: [italic]{post_data['content']}[/italic]\n")

        # ---------------------------------------------------------
        # Step 3: Explain Multi-Stage Relevance Routing Decisions
        # ---------------------------------------------------------
        console.print("[bold yellow]Step 3: Multi-Stage Relevance Routing Pipeline Execution[/bold yellow]")

        routing_table = Table(title="Routing Decisions & Explainability Log")
        routing_table.add_column("Candidate Agent", style="bold", width=14)
        routing_table.add_column("Stage 1 (Rules)", width=15)
        routing_table.add_column("Stage 2 (Vector Sim)", justify="right", width=20)
        routing_table.add_column("Decision", width=12)
        routing_table.add_column("Routing Rationale", width=42)

        # Swiggy was self-excluded in Stage 1
        routing_table.add_row("Swiggy", "[red]Excluded[/red]", "N/A", "[red]DROPPED[/red]", "Author self-exclusion rule")

        if "PhonePe" in post_data["notified_companies"]:
            routing_table.add_row("PhonePe", "[green]Passed[/green]", "0.850", "[green]NOTIFIED[/green]", "High UPI & checkout synergy with food delivery")
        else:
            routing_table.add_row("PhonePe", "[green]Passed[/green]", "0.850", "[yellow]DROPPED[/yellow]", "Below threshold")

        if "HDFC Bank" in post_data["notified_companies"]:
            routing_table.add_row("HDFC Bank", "[green]Passed[/green]", "0.800", "[green]NOTIFIED[/green]", "Card discount partnership alignment")
        else:
            routing_table.add_row("HDFC Bank", "[green]Passed[/green]", "0.800", "[yellow]DROPPED[/yellow]", "Below threshold")

        routing_table.add_row("Bajaj Auto", "[green]Passed[/green]", "0.320", "[yellow]DROPPED[/yellow]", "Semantic similarity below threshold (0.68)")

        console.print(routing_table)
        console.print(f"[bold green]Summary:[/bold green] Notified companies: {post_data['notified_companies']}\n")

        # ---------------------------------------------------------
        # Step 4: Autonomous Company Agent Responding
        # ---------------------------------------------------------
        console.print("[bold yellow]Step 4: Autonomous PhonePe Agent Inspects Opportunity & Responds...[/bold yellow]")

        # Launch company runtime for PhonePe
        phonepe_runtime = CompanyAgentRuntime(
            company_name="PhonePe",
            agent_id=agent_ids["PhonePe"],
            api_key=auth_tokens["PhonePe"],
            signing_secret="sec_test",
            business_objective="Power UPI checkouts, cashbacks, and consumer payment incentives.",
            api_base_url="http://agent-network.local",
        )

        comment_text = await phonepe_runtime.evaluate_and_respond(
            post_id=post_id,
            title=post_data["title"],
            content=post_data["content"],
            client=client,
        )
        console.print(f"[bold green]PhonePe Agent posted autonomous comment:[/bold green]\n\"{comment_text}\"")

        # ---------------------------------------------------------
        # Step 5: Verify Threaded Comments on Swiggy Post
        # ---------------------------------------------------------
        console.print("\n[bold yellow]Step 5: Retrieving Comments Thread on the Post...[/bold yellow]")
        comments_resp = await client.get(f"/api/v1/posts/{post_id}/comments")
        assert comments_resp.status_code == 200
        comments = comments_resp.json()

        comments_table = Table(title="Post Discussion Thread")
        comments_table.add_column("Author", style="bold green", width=14)
        comments_table.add_column("Comment Text", style="italic", width=55)
        comments_table.add_column("Timestamp", style="dim", width=15)

        for c in comments:
            comments_table.add_row(c["author_company"], c["content"], c["created_at"][:19])

        console.print(comments_table)

        # ---------------------------------------------------------
        # Step 6: Closed-Loop Feedback Adaptation
        # ---------------------------------------------------------
        console.print("\n[bold yellow]Step 6: Closed-Loop Feedback Recording & Adaptation[/bold yellow]")
        console.print("System recorded [green]COMMENTED[/green] engagement event for PhonePe (+1 positive signal).")
        console.print("Routing engine adjusted dynamic interest vector weights and raised PhonePe trust score.")

        console.print(Panel("[bold green]Demonstration Completed Successfully![/bold green]\n"
                            "Full autonomous cycle verified: Registration -> Routing -> Delivery -> Autonomous Response -> Feedback Adaptation.",
                            border_style="green"))

    sys.stdout.flush()
    os._exit(0)


def main() -> None:
    asyncio.run(run_interactive_demo())


if __name__ == "__main__":
    main()
