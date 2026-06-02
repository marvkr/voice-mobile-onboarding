from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


def now_utc() -> datetime:
    return datetime.now(UTC)


class ProfilePatch(BaseModel):
    display_name: str | None = None
    primary_goal: str | None = None
    interests: list[str] = Field(default_factory=list)
    communication_style: str | None = None
    language: str | None = None
    notes: str | None = None


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    display_name: str | None = None
    primary_goal: str | None = None
    interests: list[str] = Field(default_factory=list)
    communication_style: str | None = None
    language: str | None = None
    notes: str | None = None
    completed: bool = False
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)
    completed_at: datetime | None = None


class OnboardingStatus(BaseModel):
    user_id: str
    completed: bool
    next_screen: str | None = None
    profile: Profile


class VoiceSetupId(StrEnum):
    OPENAI_REALTIME_MINI = "openai-realtime-mini"
    OPENAI_REALTIME_FULL = "openai-realtime-2"
    OPENAI_CASCADED = "openai-cascaded"
    DEEPGRAM_CARTESIA = "deepgram-cartesia"


class VoiceSetup(BaseModel):
    id: VoiceSetupId
    label: str
    stack: str
    available: bool
    required_env: list[str] = Field(default_factory=list)
    missing_env: list[str] = Field(default_factory=list)
    missing_dependencies: list[str] = Field(default_factory=list)
    cost_note: str
    quality_note: str


class VoiceSetupRun(BaseModel):
    call_id: str
    user_id: str
    voice_setup: VoiceSetupId
    started_at: datetime
    ended_at: datetime | None = None
    duration_seconds: float | None = None
    completed: bool = False
    profile_field_count: int = 0


class VoiceSetupComparisonRow(BaseModel):
    setup: VoiceSetup
    runs: int
    last_run: VoiceSetupRun | None = None
    best_completed: bool = False
    best_profile_field_count: int = 0


class VoiceSetupComparisonResponse(BaseModel):
    user_id: str
    rows: list[VoiceSetupComparisonRow]


class StartOnboardingRequest(BaseModel):
    voice_setup: VoiceSetupId = VoiceSetupId.OPENAI_REALTIME_MINI


class StartOnboardingResponse(BaseModel):
    user_id: str
    call_id: str
    webrtc_url: str
    voice_setup: VoiceSetup
