from threading import Lock
from uuid import uuid4

from app.models import (
    OnboardingStatus,
    Profile,
    ProfilePatch,
    VoiceSetup,
    VoiceSetupComparisonResponse,
    VoiceSetupComparisonRow,
    VoiceSetupId,
    VoiceSetupRun,
    now_utc,
)


def _profile_field_count(profile: Profile) -> int:
    return sum(
        [
            bool(profile.display_name),
            bool(profile.primary_goal),
            bool(profile.interests),
            bool(profile.communication_style),
            bool(profile.language),
            bool(profile.notes),
        ]
    )


class InMemoryProfileStore:
    """Prototype store; replace with Postgres once auth and schema are fixed."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._profiles: dict[str, Profile] = {}
        self._voice_setup_runs: dict[str, VoiceSetupRun] = {}
        self._voice_setup_run_ids_by_user: dict[str, list[str]] = {}

    def ensure_profile(self, user_id: str) -> Profile:
        with self._lock:
            profile = self._profiles.get(user_id)
            if profile is None:
                profile = Profile(user_id=user_id)
                self._profiles[user_id] = profile
            return profile

    def upsert_profile(self, user_id: str, patch: ProfilePatch) -> Profile:
        with self._lock:
            profile = self._profiles.get(user_id) or Profile(user_id=user_id)
            updates = patch.model_dump(exclude_unset=True)
            if updates.get("interests") == []:
                updates.pop("interests")
            if "interests" in updates and updates["interests"]:
                updates["interests"] = sorted(set(profile.interests + updates["interests"]))
            profile = profile.model_copy(update={**updates, "updated_at": now_utc()})
            self._profiles[user_id] = profile
            return profile

    def complete_onboarding(self, user_id: str) -> Profile:
        with self._lock:
            profile = self._profiles.get(user_id) or Profile(user_id=user_id)
            completed_at = now_utc()
            profile = profile.model_copy(
                update={"completed": True, "completed_at": completed_at, "updated_at": completed_at}
            )
            self._profiles[user_id] = profile
            return profile

    def reset_profile(self, user_id: str) -> Profile:
        with self._lock:
            profile = Profile(user_id=user_id)
            self._profiles[user_id] = profile
            return profile

    def start_voice_setup_run(self, user_id: str, voice_setup: VoiceSetupId) -> VoiceSetupRun:
        with self._lock:
            call_id = str(uuid4())
            run = VoiceSetupRun(
                call_id=call_id,
                user_id=user_id,
                voice_setup=voice_setup,
                started_at=now_utc(),
            )
            self._voice_setup_runs[call_id] = run
            self._voice_setup_run_ids_by_user.setdefault(user_id, []).append(call_id)
            return run

    def finish_voice_setup_run(self, user_id: str, call_id: str) -> VoiceSetupRun | None:
        with self._lock:
            run = self._voice_setup_runs.get(call_id)
            if run is None or run.user_id != user_id:
                return None
            if run.ended_at is not None:
                return run

            profile = self._profiles.get(user_id) or Profile(user_id=user_id)
            ended_at = now_utc()
            run = run.model_copy(
                update={
                    "ended_at": ended_at,
                    "duration_seconds": round((ended_at - run.started_at).total_seconds(), 2),
                    "completed": profile.completed,
                    "profile_field_count": _profile_field_count(profile),
                }
            )
            self._voice_setup_runs[call_id] = run
            return run

    def compare_voice_setups(self, user_id: str, setups: list[VoiceSetup]) -> VoiceSetupComparisonResponse:
        with self._lock:
            run_ids = self._voice_setup_run_ids_by_user.get(user_id, [])
            runs = [self._voice_setup_runs[run_id] for run_id in run_ids if run_id in self._voice_setup_runs]

        rows = []
        for setup in setups:
            setup_runs = [run for run in runs if run.voice_setup == setup.id]
            last_run = max(setup_runs, key=lambda run: run.started_at, default=None)
            rows.append(
                VoiceSetupComparisonRow(
                    setup=setup,
                    runs=len(setup_runs),
                    last_run=last_run,
                    best_completed=any(run.completed for run in setup_runs),
                    best_profile_field_count=max((run.profile_field_count for run in setup_runs), default=0),
                )
            )

        return VoiceSetupComparisonResponse(user_id=user_id, rows=rows)

    def status(self, user_id: str) -> OnboardingStatus:
        profile = self.ensure_profile(user_id)
        return OnboardingStatus(
            user_id=user_id,
            completed=profile.completed,
            next_screen="home" if profile.completed else None,
            profile=profile,
        )


profile_store = InMemoryProfileStore()
