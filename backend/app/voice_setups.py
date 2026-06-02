from __future__ import annotations

from importlib.util import find_spec

from app.config import Settings
from app.models import VoiceSetup, VoiceSetupId


def resolve_voice_setup_id(value: str | VoiceSetupId | None) -> VoiceSetupId:
    if value is None:
        return VoiceSetupId.OPENAI_REALTIME_MINI
    if isinstance(value, VoiceSetupId):
        return value
    return VoiceSetupId(value)


def get_voice_setups(settings: Settings) -> list[VoiceSetup]:
    return [
        _openai_realtime_mini(settings),
        _openai_realtime_full(settings),
        _openai_cascaded(settings),
        _deepgram_cartesia(settings),
    ]


def get_voice_setup(settings: Settings, setup_id: VoiceSetupId) -> VoiceSetup:
    return next(setup for setup in get_voice_setups(settings) if setup.id == setup_id)


def _missing_env(settings: Settings, names: list[str]) -> list[str]:
    values = {
        "OPENAI_API_KEY": settings.openai_api_key,
        "DEEPGRAM_API_KEY": settings.deepgram_api_key,
        "CARTESIA_API_KEY": settings.cartesia_api_key,
        "CARTESIA_VOICE_ID": settings.cartesia_voice_id,
    }
    return [name for name in names if not values.get(name)]


def _openai_realtime_mini(settings: Settings) -> VoiceSetup:
    required_env = ["OPENAI_API_KEY"]
    missing_env = _missing_env(settings, required_env)
    return VoiceSetup(
        id=VoiceSetupId.OPENAI_REALTIME_MINI,
        label="OpenAI Realtime Mini",
        stack=f"Native speech-to-speech, {settings.openai_realtime_mini_model}",
        available=not missing_env,
        required_env=required_env,
        missing_env=missing_env,
        cost_note="Cheapest OpenAI native realtime setup; default MVP candidate.",
        quality_note="Lower tool-calling margin than the full realtime model, so this needs evals.",
    )


def _openai_realtime_full(settings: Settings) -> VoiceSetup:
    required_env = ["OPENAI_API_KEY"]
    missing_env = _missing_env(settings, required_env)
    return VoiceSetup(
        id=VoiceSetupId.OPENAI_REALTIME_FULL,
        label="OpenAI Realtime 2",
        stack=f"Native speech-to-speech, {settings.openai_realtime_full_model}",
        available=not missing_env,
        required_env=required_env,
        missing_env=missing_env,
        cost_note="Highest-cost OpenAI path; use as quality benchmark and fallback.",
        quality_note="Best instruction following and tool reliability among the OpenAI voice setups.",
    )


def _openai_cascaded(settings: Settings) -> VoiceSetup:
    required_env = ["OPENAI_API_KEY"]
    missing_env = _missing_env(settings, required_env)
    return VoiceSetup(
        id=VoiceSetupId.OPENAI_CASCADED,
        label="OpenAI Cascaded",
        stack=(
            f"{settings.openai_cascaded_stt_model} STT -> "
            f"{settings.openai_cascaded_llm_model} LLM -> "
            f"{settings.openai_cascaded_tts_model} TTS"
        ),
        available=not missing_env,
        required_env=required_env,
        missing_env=missing_env,
        cost_note="Tests cascaded architecture with the same OpenAI key before adding more vendors.",
        quality_note="More tunable and swappable than native realtime, but may have higher turn latency.",
    )


def _deepgram_cartesia(settings: Settings) -> VoiceSetup:
    required_env = ["OPENAI_API_KEY", "DEEPGRAM_API_KEY", "CARTESIA_API_KEY", "CARTESIA_VOICE_ID"]
    missing_env = _missing_env(settings, required_env)
    missing_dependencies = []
    if find_spec("deepgram") is None:
        missing_dependencies.append("pipecat-ai[deepgram]")

    return VoiceSetup(
        id=VoiceSetupId.DEEPGRAM_CARTESIA,
        label="Deepgram + Cartesia",
        stack=f"{settings.deepgram_stt_model} STT -> OpenAI LLM -> {settings.cartesia_tts_model} TTS",
        available=not missing_env and not missing_dependencies,
        required_env=required_env,
        missing_env=missing_env,
        missing_dependencies=missing_dependencies,
        cost_note="Most realistic lower-cost production candidate once provider keys are configured.",
        quality_note="Strong STT plus fast TTS; more moving parts than native realtime.",
    )
