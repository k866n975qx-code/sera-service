from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from app.core.db import Base


class WhoopToken(Base):
    __tablename__ = "whoop_token"

    id = Column(Integer, primary_key=True)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=True)
    token_type = Column(String, nullable=True)
    scope = Column(String, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)