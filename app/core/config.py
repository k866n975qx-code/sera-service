import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    POSTGRES_DSN = os.getenv("POSTGRES_DSN")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")

    # Path to MyWhoop auto-refreshing token
    WHOOP_CREDENTIALS_PATH = "/home/jose/mywhoop/credentials.json"


settings = Settings()