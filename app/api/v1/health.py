from fastapi import APIRouter
from app.core.config import settings
from app.core.db import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "db": engine is not None,
    }