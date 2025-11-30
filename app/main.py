from fastapi import FastAPI

from app.core.db import Base, engine
from app.api.v1.health import router as health_router
from app.api.v1.apple import router as apple_router
from app.api.v1.whoop import router as whoop_router
from app.api.v1.snapshot import router as snapshot_router
from app.api.v1.whoop_oauth import router as whoop_oauth_router
from app import models  # ensure models are registered


app = FastAPI(title="SERA", version="0.1.0")

if engine:
    Base.metadata.create_all(bind=engine)

app.include_router(health_router, prefix="/v1")
app.include_router(apple_router, prefix="/v1")
app.include_router(whoop_router, prefix="/v1")
app.include_router(snapshot_router, prefix="/v1")

# OAuth routes have no /v1 prefix so callback path is /whoop/callback
app.include_router(whoop_oauth_router)