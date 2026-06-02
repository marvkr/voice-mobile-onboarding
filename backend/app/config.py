from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_realtime_model: str | None = Field(default=None, alias="OPENAI_REALTIME_MODEL")
    openai_realtime_mini_model: str = Field(default="gpt-realtime-mini", alias="OPENAI_REALTIME_MINI_MODEL")
    openai_realtime_full_model: str = Field(default="gpt-realtime-2", alias="OPENAI_REALTIME_FULL_MODEL")
    openai_cascaded_stt_model: str = Field(default="gpt-4o-mini-transcribe", alias="OPENAI_CASCADED_STT_MODEL")
    openai_cascaded_llm_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_CASCADED_LLM_MODEL")
    openai_cascaded_tts_model: str = Field(default="gpt-4o-mini-tts", alias="OPENAI_CASCADED_TTS_MODEL")
    openai_cascaded_tts_voice: str = Field(default="marin", alias="OPENAI_CASCADED_TTS_VOICE")
    deepgram_api_key: str | None = Field(default=None, alias="DEEPGRAM_API_KEY")
    deepgram_stt_model: str = Field(default="nova-3-general", alias="DEEPGRAM_STT_MODEL")
    cartesia_api_key: str | None = Field(default=None, alias="CARTESIA_API_KEY")
    cartesia_tts_model: str = Field(default="sonic-3.5", alias="CARTESIA_TTS_MODEL")
    cartesia_voice_id: str | None = Field(default=None, alias="CARTESIA_VOICE_ID")
    public_api_base_url: str | None = Field(default=None, alias="PUBLIC_API_BASE_URL")
    allowed_origins: str = Field(default="*", alias="ALLOWED_ORIGINS")
    ice_servers: str = Field(default="stun:stun.l.google.com:19302", alias="ICE_SERVERS")
    max_onboarding_call_seconds: int = Field(default=120, alias="MAX_ONBOARDING_CALL_SECONDS")

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
