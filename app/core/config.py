import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    POSTGRES_DSN: str
    ENVIRONMENT: str = "local"

    # Base URL for WHOOP developer API (used by whoop.py)
    WHOOP_API_BASE: str = "https://api.prod.whoop.com"

    # Path to MyWhoop auto-refreshing token
    WHOOP_CREDENTIALS_PATH = "/home/jose/mywhoop/credentials.json"


settings = Settings()