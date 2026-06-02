from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_realtime_model: str | None = Field(default=None, alias="OPENAI_REALTIME_MODEL")
    public_api_base_url: str | None = Field(default=None, alias="PUBLIC_API_BASE_URL")
    allowed_origins: str = Field(default="*", alias="ALLOWED_ORIGINS")
    ice_servers: str = Field(default="stun:stun.l.google.com:19302", alias="ICE_SERVERS")

    @property
    def cors_origins(self) -> list[str]:
        if self.allowed_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def webrtc_ice_servers(self) -> list[str]:
        return [server.strip() for server in self.ice_servers.split(",") if server.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

