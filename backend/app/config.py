import os


class Settings:
    """Runtime configuration. Values come from environment variables
    (see docker-compose.yml / .env)."""

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://shipyard:shipyard@db:5432/shipyard",
    )

    # Comma separated list of origins, "*" allows everything (dev convenience).
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")

    @property
    def cors_origin_list(self) -> list[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
