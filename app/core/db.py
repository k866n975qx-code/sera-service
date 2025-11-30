from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

Base = declarative_base()

engine = None
SessionLocal = None

if settings.POSTGRES_DSN:
    engine = create_engine(settings.POSTGRES_DSN, future=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)