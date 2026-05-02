import hashlib
import hmac
import os
import secrets
import uuid
from typing import Optional

import redis.asyncio as aioredis
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .models import ApiKey, Tenant

_redis: Optional[aioredis.Redis] = None


def set_redis(r: aioredis.Redis) -> None:
    global _redis
    _redis = r


def generate_api_key() -> tuple[str, str, str]:
    """Return (full_key, prefix, salt). Only full_key is shown once."""
    raw = secrets.token_urlsafe(32)
    prefix = raw[:8]
    salt = secrets.token_hex(16)
    full_key = f"sk_live_{prefix}_{raw}"
    return full_key, prefix, salt


async def verify_api_key(
    x_stylesync_key: Optional[str] = Header(None, alias="X-StyleSync-Key"),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    if not x_stylesync_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")

    cache_key = f"stylesync:apikey:{hashlib.sha256(x_stylesync_key.encode()).hexdigest()}"
    if _redis:
        cached = await _redis.get(cache_key)
        if cached:
            return uuid.UUID(cached.decode())

    parts = x_stylesync_key.split("_", 3)
    if len(parts) < 4:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key format")
    prefix = parts[2]

    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_prefix == prefix,
            ApiKey.revoked_at.is_(None),
        )
    )
    candidates = result.scalars().all()

    tenant_id = None
    for candidate in candidates:
        computed = hashlib.sha256(x_stylesync_key.encode()).digest()
        if hmac.compare_digest(candidate.key_hash, computed):
            tenant_id = candidate.tenant_id
            from .models import utcnow
            candidate.last_used_at = utcnow()
            await db.commit()
            break

    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API key")

    if _redis:
        await _redis.setex(cache_key, 300, str(tenant_id))

    return tenant_id
