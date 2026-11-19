from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "DevOpsPilot AI"
    environment: str = "development"
    database_url: str = "sqlite:///./devopspilot.db"
    jwt_secret: str = "CHANGE_ME_TO_A_LONG_RANDOM_SECRET"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    prometheus_url: str = "http://prometheus:9090"
    loki_url: str = "http://loki:3100"
    jaeger_url: str = "http://jaeger:16686"
    monitored_api_url: str = "http://monitored-api:8001"
    redis_url: str = "redis://redis:6379/0"
    controller_url: str = "http://infrastructure-controller:8002"
    controller_token: str = ""
    allowed_demo_containers: str = "demo-postgres,demo-api,cpu-stressor,memory-stressor"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def allowed_containers(self) -> set[str]:
        return {item.strip() for item in self.allowed_demo_containers.split(",") if item.strip()}

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()
