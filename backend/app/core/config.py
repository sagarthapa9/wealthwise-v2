from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "WealthWise API"
    database_url: str = "postgresql+asyncpg://wealthwise:wealthwise@db:5432/wealthwise"
    debug: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
