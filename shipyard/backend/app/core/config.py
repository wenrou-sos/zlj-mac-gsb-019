from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """运行参数全部可通过环境变量覆盖（Docker 编排里注入）。"""

    app_name: str = "船舶维修坞期管理平台"
    # 默认指向 docker-compose 中的 postgres 服务；本地直跑无 PG 时回退 SQLite
    database_url: str = "postgresql+psycopg2://shipyard:shipyard@db:5432/shipyard"
    cors_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(env_file=".env", env_prefix="SHIPYARD_", extra="ignore")


settings = Settings()
