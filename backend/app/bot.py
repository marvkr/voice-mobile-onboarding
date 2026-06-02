from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from app.config import get_settings
from app.models import ProfilePatch, VoiceSetupId
from app.onboarding_prompt import ONBOARDING_SYSTEM_INSTRUCTION
from app.profile_store import InMemoryProfileStore


async def run_onboarding_bot(
    webrtc_connection: object,
    user_id: str,
    store: InMemoryProfileStore,
    voice_setup_id: VoiceSetupId | str = VoiceSetupId.OPENAI_REALTIME_MINI,
    call_id: str | None = None,
) -> None:
    settings = get_settings()
    if not settings.openai_api_key:
        logger.error("OPENAI_API_KEY is not configured; cannot start onboarding bot")
        if call_id:
            store.finish_voice_setup_run(user_id, call_id)
        return

    voice_setup_id = VoiceSetupId(voice_setup_id)

    from pipecat.adapters.schemas.tools_schema import ToolsSchema
    from pipecat.frames.frames import LLMRunFrame, LLMMessagesAppendFrame
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.worker import PipelineParams, PipelineWorker
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
    from pipecat.transports.base_transport import TransportParams
    from pipecat.workers.runner import WorkerRunner

    try:
        from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
    except ImportError:  # Older Pipecat releases used a different module path.
        from pipecat.transports.network.small_webrtc import SmallWebRTCTransport

    async def save_profile(
        params,
        display_name: str | None = None,
        primary_goal: str | None = None,
        interests: list[str] | None = None,
        communication_style: str | None = None,
        language: str | None = None,
        notes: str | None = None,
    ) -> None:
        """Save Profile facts learned during the Onboarding Call.

        Args:
            display_name: The name the user wants the app to use.
            primary_goal: The main outcome the user wants from the app.
            interests: Specific app use cases, topics, or preferences the user mentioned.
            communication_style: The tone or cadence the user prefers.
            language: The spoken language the user prefers.
            notes: Short extra context that does not fit the other fields.
        """
        patch_data = {
            "display_name": display_name,
            "primary_goal": primary_goal,
            "communication_style": communication_style,
            "language": language,
            "notes": notes,
        }
        patch_data = {key: value for key, value in patch_data.items() if value is not None}
        if interests:
            patch_data["interests"] = interests

        profile = store.upsert_profile(user_id, ProfilePatch(**patch_data))
        await params.result_callback({"ok": True, "profile": profile.model_dump(mode="json")})

    async def finish_onboarding(params) -> None:
        """Finish the Onboarding Call and send the user to the home screen."""
        profile = store.complete_onboarding(user_id)
        await params.result_callback(
            {
                "ok": True,
                "next_screen": "home",
                "profile": profile.model_dump(mode="json"),
            }
        )

    tools = ToolsSchema(standard_tools=[save_profile, finish_onboarding])
    context = LLMContext(tools=tools)
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(context)
    transport = SmallWebRTCTransport(
        params=TransportParams(audio_in_enabled=True, audio_out_enabled=True),
        webrtc_connection=webrtc_connection,
    )

    if voice_setup_id in {VoiceSetupId.OPENAI_REALTIME_MINI, VoiceSetupId.OPENAI_REALTIME_FULL}:
        pipeline = _build_openai_realtime_pipeline(
            voice_setup_id=voice_setup_id,
            settings=settings,
            transport=transport,
            user_aggregator=user_aggregator,
            assistant_aggregator=assistant_aggregator,
            save_profile=save_profile,
            finish_onboarding=finish_onboarding,
        )
        initial_frame: Any = LLMRunFrame()
    elif voice_setup_id == VoiceSetupId.OPENAI_CASCADED:
        pipeline = _build_openai_cascaded_pipeline(
            settings=settings,
            transport=transport,
            user_aggregator=user_aggregator,
            assistant_aggregator=assistant_aggregator,
            save_profile=save_profile,
            finish_onboarding=finish_onboarding,
        )
        initial_frame = _start_cascaded_call_frame(LLMMessagesAppendFrame)
    elif voice_setup_id == VoiceSetupId.DEEPGRAM_CARTESIA:
        pipeline = _build_deepgram_cartesia_pipeline(
            settings=settings,
            transport=transport,
            user_aggregator=user_aggregator,
            assistant_aggregator=assistant_aggregator,
            save_profile=save_profile,
            finish_onboarding=finish_onboarding,
        )
        initial_frame = _start_cascaded_call_frame(LLMMessagesAppendFrame)
    else:
        raise ValueError(f"Unsupported voice setup: {voice_setup_id}")

    task = PipelineWorker(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        idle_timeout_secs=settings.max_onboarding_call_seconds,
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client) -> None:
        logger.info(
            "Onboarding Call connected for user_id={} voice_setup={}",
            user_id,
            voice_setup_id.value,
        )
        await task.queue_frames([initial_frame])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client) -> None:
        logger.info("Onboarding Call disconnected for user_id={}", user_id)
        await task.cancel()

    runner = WorkerRunner(handle_sigint=False)
    try:
        await asyncio.wait_for(runner.run(task), timeout=settings.max_onboarding_call_seconds)
    except TimeoutError:
        logger.info(
            "Onboarding Call reached max duration for user_id={} voice_setup={}",
            user_id,
            voice_setup_id.value,
        )
        await task.cancel()
    finally:
        if call_id:
            store.finish_voice_setup_run(user_id, call_id)


def _build_openai_realtime_pipeline(
    *,
    voice_setup_id: VoiceSetupId,
    settings: Any,
    transport: Any,
    user_aggregator: Any,
    assistant_aggregator: Any,
    save_profile: Any,
    finish_onboarding: Any,
) -> Any:
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.services.openai.realtime.events import (
        AudioConfiguration,
        AudioInput,
        InputAudioNoiseReduction,
        InputAudioTranscription,
        SemanticTurnDetection,
        SessionProperties,
    )
    from pipecat.services.openai.realtime.llm import OpenAIRealtimeLLMService

    model = (
        settings.openai_realtime_mini_model
        if voice_setup_id == VoiceSetupId.OPENAI_REALTIME_MINI
        else settings.openai_realtime_full_model
    )

    llm = OpenAIRealtimeLLMService(
        api_key=settings.openai_api_key,
        settings=OpenAIRealtimeLLMService.Settings(
            model=model,
            system_instruction=ONBOARDING_SYSTEM_INSTRUCTION,
            session_properties=SessionProperties(
                audio=AudioConfiguration(
                    input=AudioInput(
                        transcription=InputAudioTranscription(),
                        turn_detection=SemanticTurnDetection(),
                        noise_reduction=InputAudioNoiseReduction(type="near_field"),
                    )
                )
            ),
        ),
    )
    llm.register_direct_function(save_profile)
    llm.register_direct_function(finish_onboarding)

    return Pipeline(
        [
            transport.input(),
            user_aggregator,
            llm,
            transport.output(),
            assistant_aggregator,
        ]
    )


def _build_openai_cascaded_pipeline(
    *,
    settings: Any,
    transport: Any,
    user_aggregator: Any,
    assistant_aggregator: Any,
    save_profile: Any,
    finish_onboarding: Any,
) -> Any:
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.services.openai.llm import OpenAILLMService
    from pipecat.services.openai.stt import OpenAISTTService
    from pipecat.services.openai.tts import OpenAITTSService
    from pipecat.transcriptions.language import Language

    stt = OpenAISTTService(
        api_key=settings.openai_api_key,
        settings=OpenAISTTService.Settings(
            model=settings.openai_cascaded_stt_model,
            language=Language.EN,
        ),
    )
    llm = OpenAILLMService(
        api_key=settings.openai_api_key,
        settings=OpenAILLMService.Settings(
            model=settings.openai_cascaded_llm_model,
            system_instruction=ONBOARDING_SYSTEM_INSTRUCTION,
            max_completion_tokens=180,
        ),
    )
    llm.register_direct_function(save_profile)
    llm.register_direct_function(finish_onboarding)
    tts = OpenAITTSService(
        api_key=settings.openai_api_key,
        settings=OpenAITTSService.Settings(
            model=settings.openai_cascaded_tts_model,
            voice=settings.openai_cascaded_tts_voice,
            instructions="Sound warm, concise, and like a calm mobile onboarding guide.",
        ),
    )

    return _build_cascaded_pipeline(transport, stt, user_aggregator, llm, tts, assistant_aggregator)


def _build_deepgram_cartesia_pipeline(
    *,
    settings: Any,
    transport: Any,
    user_aggregator: Any,
    assistant_aggregator: Any,
    save_profile: Any,
    finish_onboarding: Any,
) -> Any:
    from pipecat.services.cartesia.tts import CartesiaTTSService
    from pipecat.services.deepgram.stt import DeepgramSTTService
    from pipecat.services.openai.llm import OpenAILLMService
    from pipecat.transcriptions.language import Language

    stt = DeepgramSTTService(
        api_key=settings.deepgram_api_key,
        settings=DeepgramSTTService.Settings(
            model=settings.deepgram_stt_model,
            language=Language.EN,
        ),
    )
    llm = OpenAILLMService(
        api_key=settings.openai_api_key,
        settings=OpenAILLMService.Settings(
            model=settings.openai_cascaded_llm_model,
            system_instruction=ONBOARDING_SYSTEM_INSTRUCTION,
            max_completion_tokens=180,
        ),
    )
    llm.register_direct_function(save_profile)
    llm.register_direct_function(finish_onboarding)
    tts = CartesiaTTSService(
        api_key=settings.cartesia_api_key,
        voice_id=settings.cartesia_voice_id,
        model=settings.cartesia_tts_model,
    )

    return _build_cascaded_pipeline(transport, stt, user_aggregator, llm, tts, assistant_aggregator)


def _build_cascaded_pipeline(
    transport: Any,
    stt: Any,
    user_aggregator: Any,
    llm: Any,
    tts: Any,
    assistant_aggregator: Any,
) -> Any:
    from pipecat.pipeline.pipeline import Pipeline

    return Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )


def _start_cascaded_call_frame(frame_class: Any) -> Any:
    return frame_class(
        messages=[
            {
                "role": "developer",
                "content": "Greet the user briefly and start the voice onboarding call now.",
            }
        ],
        run_llm=True,
    )
