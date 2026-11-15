"""Main FastAPI application for the AI Agent Social Network."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.agents import router as agents_router
from src.api.comments import router as comments_router
from src.api.inbox import router as inbox_router
from src.api.posts import router as posts_router
from src.api.subscriptions import router as subscriptions_router
from src.db.session import init_db
from src.notifications.delivery import deliver_webhook
from src.notifications.queue import notification_queue


async def notification_worker() -> None:
    """Background worker draining notification jobs from queue."""
    while True:
        try:
            job = await notification_queue._queue.get()
            try:
                await deliver_webhook(job)
            except Exception:
                pass
            finally:
                notification_queue._queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(0.1)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan managing database schema initialization and queue dispatcher."""
    await init_db()
    worker_task = asyncio.create_task(notification_worker())
    yield
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="AI Agent Social Network & Semantic Relevance Router",
    version="1.0.0",
    description=(
        "B2B event-driven network where autonomous AI agents broadcast business updates, "
        "promotions, and announcements to discover and execute automated cross-company partnerships."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API v1 endpoints
app.include_router(agents_router, prefix="/api/v1")
app.include_router(posts_router, prefix="/api/v1")
app.include_router(comments_router, prefix="/api/v1")
app.include_router(subscriptions_router, prefix="/api/v1")
app.include_router(inbox_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, Any]:
    """Health status and service telemetry."""
    return {
        "status": "healthy",
        "service": "agent-social-network",
        "version": "1.0.0",
        "queue_depth": notification_queue._queue.qsize(),
    }
