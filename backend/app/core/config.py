from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "WealthWise API"
    database_url: str = "postgresql+asyncpg://wealthwise:wealthwise@db:5432/wealthwise"
    debug: bool = False

    # DeepSeek LLM configuration
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # Ticker data provider
    eodhd_api_key: str = ""

    # CORS — comma-separated allowed origins (empty = deny cross-origin)
    cors_origins: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
