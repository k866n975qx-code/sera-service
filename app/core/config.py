import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    POSTGRES_DSN = os.getenv("POSTGRES_DSN")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")

    # WHOOP OAuth
    WHOOP_CLIENT_ID = os.getenv("WHOOP_CLIENT_ID")
    WHOOP_CLIENT_SECRET = os.getenv("WHOOP_CLIENT_SECRET")
    WHOOP_REDIRECT_URI = os.getenv("WHOOP_REDIRECT_URI")

    # Official WHOOP OAuth endpoints
    # from: https://developer.whoop.com/docs/developing/oauth/ and API docs  [oai_citation:7‡WHOOP Developer](https://developer.whoop.com/docs/developing/oauth/?utm_source=chatgpt.com)
    WHOOP_AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
    WHOOP_TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"

    # API base for resource endpoints (v2)
    WHOOP_API_BASE = "https://api.prod.whoop.com"


settings = Settings()