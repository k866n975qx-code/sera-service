from typing import Any, Dict

from fastapi import APIRouter

router = APIRouter(tags=["apple-health"])


@router.post("/v1/apple-health")
async def apple_health(payload: Dict[str, Any]):
    # Later we can parse `payload` into apple_health_daily, etc.
    return {"status": "ok"}