from threading import Lock

from app.models import OnboardingStatus, Profile, ProfilePatch, now_utc


class InMemoryProfileStore:
    """Prototype store; replace with Postgres once auth and schema are fixed."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._profiles: dict[str, Profile] = {}

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

    def status(self, user_id: str) -> OnboardingStatus:
        profile = self.ensure_profile(user_id)
        return OnboardingStatus(
            user_id=user_id,
            completed=profile.completed,
            next_screen="home" if profile.completed else None,
            profile=profile,
        )


profile_store = InMemoryProfileStore()
