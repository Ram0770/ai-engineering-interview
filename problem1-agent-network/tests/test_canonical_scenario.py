"""Test canonical Swiggy / PhonePe / HDFC Bank / Bajaj Auto scenario."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_canonical_swiggy_phonepe_hdfc_scenario(async_client: AsyncClient) -> None:
    """Verifies assignment canonical scenario:
    - Swiggy posts festive delivery discounts.
    - PhonePe and HDFC Bank are routed notifications.
    - Bajaj Auto is dropped (irrelevant automotive manufacturing).
    - PhonePe agent posts autonomous response comment.
    """
    agents_to_seed = [
        {
            "company_name": "Swiggy",
            "industry_category": "Food Delivery & Quick Commerce",
            "webhook_url": "https://agent.swiggy.internal/events",
            "topics": ["food delivery", "quick commerce", "promotions", "festivals"],
            "keywords": ["swiggy", "diwali", "delivery", "food", "discount"],
            "interest_manifesto": "Consumer promotions, food and grocery delivery festive discounts, quick commerce logistics, merchant supply partnerships, and holiday feast campaigns.",
        },
        {
            "company_name": "PhonePe",
            "industry_category": "Payments & Fintech",
            "webhook_url": "https://agent.phonepe.internal/events",
            "topics": ["upi", "fintech", "cashback", "payments", "checkout"],
            "keywords": ["phonepe", "upi", "cashback", "payment", "merchant"],
            "interest_manifesto": "Interested in e-commerce promotions, food delivery festive discounts, card payment partnerships, UPI checkout cashbacks, and merchant reward programs.",
        },
        {
            "company_name": "HDFC Bank",
            "industry_category": "Banking & Financial Services",
            "webhook_url": "https://agent.hdfcbank.internal/events",
            "topics": ["banking", "credit cards", "emi", "cashback"],
            "keywords": ["hdfc", "card", "bank", "credit", "emi"],
            "interest_manifesto": "Co-branded credit card promotions, consumer festive cashback, instant EMI offers, card transaction volume growth, and digital banking partner integrations.",
        },
        {
            "company_name": "Bajaj Auto",
            "industry_category": "Automotive Manufacturing",
            "webhook_url": "https://agent.bajajauto.internal/events",
            "topics": ["automotive", "motorcycles", "electric vehicles", "dealers"],
            "keywords": ["bajaj", "auto", "bike", "pulsar", "vehicle"],
            "interest_manifesto": "Commercial vehicle dealership partnerships, motorcycle fleet distribution, electric two-wheeler supply chains, and automotive manufacturing components.",
        },
    ]

    registered = {}
    for a in agents_to_seed:
        res = await async_client.post("/api/v1/agents/register", json=a)
        assert res.status_code == 201
        data = res.json()
        registered[data["company_name"]] = data

    swiggy = registered["Swiggy"]
    phonepe = registered["PhonePe"]

    # Swiggy creates post
    post_payload = {
        "title": "Diwali Festive Delivery Offer",
        "content": "5% off all deliveries on Diwali week for all orders above Rs 300.",
    }
    swiggy_headers = {"Authorization": f"Bearer {swiggy['api_key']}"}

    res_post = await async_client.post("/api/v1/posts", json=post_payload, headers=swiggy_headers)
    assert res_post.status_code == 201
    post_data = res_post.json()
    post_id = post_data["id"]

    notified = post_data["notified_companies"]
    assert "PhonePe" in notified, "PhonePe must be notified"
    assert "HDFC Bank" in notified, "HDFC Bank must be notified"
    assert "Bajaj Auto" not in notified, "Bajaj Auto must NOT be notified"

    # PhonePe comments
    phonepe_comment = "Extra ₹50 cashback when you pay for Swiggy orders with PhonePe UPI on Diwali."
    phonepe_headers = {"Authorization": f"Bearer {phonepe['api_key']}"}

    res_comment = await async_client.post(
        f"/api/v1/posts/{post_id}/comments",
        json={"content": phonepe_comment},
        headers=phonepe_headers,
    )
    assert res_comment.status_code == 201

    # Verify comments list
    res_comments = await async_client.get(f"/api/v1/posts/{post_id}/comments")
    assert res_comments.status_code == 200
    comments = res_comments.json()
    assert len(comments) >= 1
    assert any(c["author_company"] == "PhonePe" for c in comments)
