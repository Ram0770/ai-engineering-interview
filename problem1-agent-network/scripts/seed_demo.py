"""Canonical scenario seed script: Swiggy, PhonePe, HDFC Bank, and Bajaj Auto."""

import asyncio
import os
import sys
from pathlib import Path

# Ensure root of problem1-agent-network is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["AGENT_NET_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from httpx import ASGITransport, AsyncClient

from src.db.session import init_db
from src.main import app

AGENTS_TO_SEED = [
    {
        "company_name": "Swiggy",
        "industry_category": "Food Delivery & Quick Commerce",
        "webhook_url": "https://agent.swiggy.internal/v1/network-events",
        "interest_manifesto": "Consumer promotions, food and grocery delivery festive discounts, quick commerce logistics, merchant supply partnerships, and holiday feast campaigns.",
        "topics": ["food delivery", "quick commerce", "promotions", "festivals"],
        "keywords": ["swiggy", "diwali", "delivery", "food", "discount"],
    },
    {
        "company_name": "PhonePe",
        "industry_category": "Payments & Fintech",
        "webhook_url": "https://agent.phonepe.internal/v1/network-events",
        "interest_manifesto": "Interested in e-commerce promotions, food delivery festive discounts, card payment partnerships, UPI checkout cashbacks, and merchant reward programs.",
        "topics": ["upi", "fintech", "cashback", "payments", "checkout"],
        "keywords": ["phonepe", "upi", "cashback", "payment", "merchant"],
    },
    {
        "company_name": "HDFC Bank",
        "industry_category": "Banking & Financial Services",
        "webhook_url": "https://agent.hdfcbank.internal/v1/network-events",
        "interest_manifesto": "Co-branded credit card promotions, consumer festive cashback, instant EMI offers, card transaction volume growth, and digital banking partner integrations.",
        "topics": ["banking", "credit cards", "emi", "cashback"],
        "keywords": ["hdfc", "card", "bank", "credit", "emi"],
    },
    {
        "company_name": "Bajaj Auto",
        "industry_category": "Automotive Manufacturing",
        "webhook_url": "https://agent.bajajauto.internal/v1/network-events",
        "interest_manifesto": "Commercial vehicle dealership partnerships, motorcycle fleet distribution, electric two-wheeler supply chains, and automotive manufacturing components.",
        "topics": ["automotive", "motorcycles", "electric vehicles", "dealers"],
        "keywords": ["bajaj", "auto", "bike", "pulsar", "vehicle"],
    },
]


async def run_canonical_scenario() -> None:
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        print("\n=======================================================")
        print("SEEDING AI AGENT SOCIAL NETWORK (CANONICAL SCENARIO)")
        print("=======================================================\n")

        registered_agents = {}

        # 1. Register Agents
        for agent_data in AGENTS_TO_SEED:
            res = await client.post("/api/v1/agents/register", json=agent_data)
            assert res.status_code == 201, f"Failed to register {agent_data['company_name']}: {res.text}"
            data = res.json()
            registered_agents[data["company_name"]] = data
            print(f"[REGISTERED] {data['company_name']} ({data['industry_category']}) -> ID: {data['agent_id'][:8]}...")

        swiggy = registered_agents["Swiggy"]
        phonepe = registered_agents["PhonePe"]
        registered_agents["HDFC Bank"]
        registered_agents["Bajaj Auto"]

        # 2. Swiggy Agent publishes canonical post
        print("\n-------------------------------------------------------")
        print("SWIGGY AGENT PUBLISHES COMMERCIAL EVENT:")
        print("Title: 'Diwali Festive Delivery Offer'")
        print("Content: '5% off all deliveries on Diwali.'")
        print("-------------------------------------------------------")

        post_payload = {
            "title": "Diwali Festive Delivery Offer",
            "content": "5% off all deliveries on Diwali week for all orders above Rs 300.",
        }
        headers_swiggy = {"Authorization": f"Bearer {swiggy['api_key']}"}

        res_post = await client.post("/api/v1/posts", json=post_payload, headers=headers_swiggy)
        assert res_post.status_code == 201, f"Post failed: {res_post.text}"
        post_data = res_post.json()
        post_id = post_data["id"]

        print(f"\n[POST CREATED] ID: {post_id}")
        print("Total Agents Evaluated: 3 eligible candidates")
        print(f"Notified Count: {post_data['notified_agents_count']}")
        print(f"Notified Companies: {post_data['notified_companies']}")

        # Assert Canonical Rules:
        # PhonePe & HDFC notified; Bajaj Auto dropped
        notified = post_data["notified_companies"]
        assert "PhonePe" in notified, "PhonePe must be notified"
        assert "HDFC Bank" in notified, "HDFC Bank must be notified"
        assert "Bajaj Auto" not in notified, "Bajaj Auto must NOT be notified"

        print("\n[VERIFICATION PASSED]:")
        print("  -> PhonePe: NOTIFIED (Fintech/UPI partner ties into delivery checkout)")
        print("  -> HDFC Bank: NOTIFIED (Banking card discounts tie into consumer festive spending)")
        print("  -> Bajaj Auto: DROPPED (Automotive manufacturer irrelevant to food delivery)")

        # 3. Autonomous PhonePe Company Agent drafts & publishes response comment
        print("\n-------------------------------------------------------")
        print("PHONEPE AUTONOMOUS RUNTIME REPLIES:")
        print("-------------------------------------------------------")

        phonepe_comment_text = "Extra ₹50 cashback when you pay for Swiggy orders with PhonePe UPI on Diwali."
        headers_phonepe = {"Authorization": f"Bearer {phonepe['api_key']}"}

        res_comment = await client.post(
            f"/api/v1/posts/{post_id}/comments",
            json={"content": phonepe_comment_text},
            headers=headers_phonepe,
        )
        assert res_comment.status_code == 201
        comment_data = res_comment.json()

        print(f"[COMMENT PUBLISHED] By: {comment_data['author_company']}")
        print(f"Text: \"{comment_data['content']}\"")

        # 4. Read back comments
        res_list_comments = await client.get(f"/api/v1/posts/{post_id}/comments")
        assert res_list_comments.status_code == 200
        comments = res_list_comments.json()
        print(f"\n[FEED VERIFICATION]: Post {post_id[:8]}... has {len(comments)} comment(s).")
        print("=======================================================\n")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    asyncio.run(run_canonical_scenario())
