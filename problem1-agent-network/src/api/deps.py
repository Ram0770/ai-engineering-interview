"""Authentication dependencies and security identity enforcement."""

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Agent, ApiKey
from src.db.session import get_db
from src.services.verification import hash_token

security_scheme = HTTPBearer(auto_error=False)


async def get_current_agent(
    credentials: HTTPAuthorizationCredentials | None = Security(security_scheme),
    session: AsyncSession = Depends(get_db),
) -> Agent:
    """Authenticates the agent via Bearer token and enforces author identity.

    SECURITY INVARIANT:
    Author identity is strictly derived from the authenticated API token.
    Never trust author_agent_id passed in HTTP request bodies.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header. Pass 'Bearer <api_key>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw_token = credentials.credentials
    key_hash = hash_token(raw_token)

    query = select(ApiKey).where(
        ApiKey.key_hash == key_hash,
        ApiKey.revoked.is_(False),
    )
    result = await session.execute(query)
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    agent = await session.get(Agent, api_key.agent_id)
    if not agent or agent.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent account is suspended or not verified.",
        )

    return agent
