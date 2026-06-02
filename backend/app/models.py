from datetime import UTC, datetime

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


class StartOnboardingResponse(BaseModel):
    user_id: str
    webrtc_url: str

