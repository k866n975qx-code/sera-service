import urllib.parse
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.models.whoop_token import WhoopToken
from typing import Optional


REFRESH_SAFETY_SECONDS = 60  # refresh 1 minute before official expiry

router = APIRouter(tags=["whoop-oauth"])


def _require_whoop_config():
    if not settings.WHOOP_CLIENT_ID or not settings.WHOOP_CLIENT_SECRET or not settings.WHOOP_REDIRECT_URI:
        raise HTTPException(500, "WHOOP OAuth not configured (check WHOOP_CLIENT_ID/SECRET/REDIRECT_URI)")


@router.get("/whoop/auth-url")
def get_whoop_auth_url():
    _require_whoop_config()

    params = {
    "client_id": settings.WHOOP_CLIENT_ID,
    "redirect_uri": settings.WHOOP_REDIRECT_URI,
    "response_type": "code",
    "scope": "offline read:profile read:recovery read:cycles read:sleep read:body_measurement",
    "state": "SERADEV123",  # MUST be 8+ chars
}
    query = urllib.parse.urlencode(params)
    auth_url = f"{settings.WHOOP_AUTH_URL}?{query}"
    return {"auth_url": auth_url}


@router.get("/whoop/callback")
def whoop_callback(code: str = Query(...), state: str | None = None):
    """
    WHOOP OAuth callback endpoint.
    Exchanges auth code for tokens and stores them in DB.
    """
    _require_whoop_config()

    if not engine or not SessionLocal:
        raise HTTPException(503, "DB not configured")

    # Exchange code for tokens
    token_url = settings.WHOOP_TOKEN_URL

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.WHOOP_REDIRECT_URI,
        "client_id": settings.WHOOP_CLIENT_ID,
        "client_secret": settings.WHOOP_CLIENT_SECRET,
    }

    with httpx.Client(timeout=10.0) as client:
        resp = client.post(token_url, data=data)
        if resp.status_code != 200:
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"WHOOP token exchange failed: {resp.text}",
            )
        payload = resp.json()

    access_token = payload.get("access_token")
    refresh_token = payload.get("refresh_token")
    token_type = payload.get("token_type")
    scope = payload.get("scope")
    expires_in = payload.get("expires_in")

    if not access_token:
        raise HTTPException(500, "WHOOP token response missing access_token")

    expires_at = None
    if expires_in:
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    db: Session = SessionLocal()
    try:
        # For now: single row, overwrite any existing token
        existing = db.query(WhoopToken).order_by(WhoopToken.id.asc()).first()

        if existing:
            existing.access_token = access_token
            existing.refresh_token = refresh_token
            existing.token_type = token_type
            existing.scope = scope
            existing.expires_at = expires_at
        else:
            row = WhoopToken(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type=token_type,
                scope=scope,
                expires_at=expires_at,
            )
            db.add(row)

        db.commit()
    finally:
        db.close()

    # Simple success response – you can later redirect to joseai.dev/whoop/success
    return {"status": "ok", "message": "WHOOP connected"}

@router.get("/whoop/test")
def whoop_test():
    """
    Test call to WHOOP API using stored access token.
    This is for dev only; remove or lock down later.
    """
    if not engine or not SessionLocal:
        raise HTTPException(503, "DB not configured")

    db: Session = SessionLocal()
    try:
        token_row = db.query(WhoopToken).order_by(WhoopToken.id.asc()).first()
        if not token_row or not token_row.access_token:
            raise HTTPException(404, "No WHOOP token stored")

        access_token = token_row.access_token
    finally:
        db.close()

    # Example WHOOP v2 endpoint – adjust if WHOOP's docs differ
    me_url = f"{settings.WHOOP_API_BASE}/developer/v2/user/profile/basic"

    with httpx.Client(timeout=10.0) as client:
        resp = client.get(
            me_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if resp.status_code != 200:
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"WHOOP API test failed: {resp.text}",
            )

        return resp.json()


def get_valid_access_token(db: Optional[Session] = None) -> str:
    """
    Central place to get a valid WHOOP access token.

    - Loads latest WhoopToken from DB
    - If expires_at is in the past or near, refreshes using refresh_token
    - Updates DB row with new tokens + expiry
    - Returns a guaranteed-fresh access_token
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        token: WhoopToken | None = (
            db.query(WhoopToken)
            .order_by(WhoopToken.id.desc())
            .first()
        )

        if token is None:
            raise HTTPException(status_code=503, detail="WHOOP not connected")


        # Otherwise, refresh the token via WHOOP OAuth
        if not token.refresh_token:
            # No refresh token stored – user must re-link WHOOP
            raise HTTPException(
                status_code=503,
                detail="WHOOP refresh token missing – please reconnect WHOOP",
            )

        token_url = settings.WHOOP_TOKEN_URL
        data = {
            "grant_type": "refresh_token",
            "refresh_token": token.refresh_token,
            "client_id": settings.WHOOP_CLIENT_ID,
            "client_secret": settings.WHOOP_CLIENT_SECRET,
            "scope": "offline read:profile read:recovery read:cycles read:sleep read:body_measurement",
        }

        with httpx.Client(timeout=10.0) as client:
            resp = client.post(token_url, data=data)
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=f"WHOOP refresh failed: {resp.text}",
                )

            payload = resp.json()
            new_access_token = payload.get("access_token")
            new_refresh_token = payload.get("refresh_token") or token.refresh_token
            expires_in = payload.get("expires_in")  # seconds

            if not new_access_token:
                raise HTTPException(
                    status_code=500,
                    detail="WHOOP refresh response missing access_token",
                )

            token.access_token = new_access_token
            token.refresh_token = new_refresh_token

            if isinstance(expires_in, (int, float)):
                token.expires_at = datetime.utcnow() + timedelta(
                    seconds=int(expires_in)
                )

            db.add(token)
            db.commit()
            db.refresh(token)

            return token.access_token

    finally:
        if close_db:
            db.close()