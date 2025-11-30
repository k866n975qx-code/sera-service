from typing import Any, Dict

from fastapi import APIRouter

router = APIRouter()


@router.post("/apple-health")
async def apple_health(payload: Dict[str, Any]):
    return {"status": "ok"}