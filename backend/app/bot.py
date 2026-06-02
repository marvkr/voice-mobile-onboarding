from __future__ import annotations

from loguru import logger

from app.config import get_settings
from app.models import ProfilePatch
from app.onboarding_prompt import ONBOARDING_SYSTEM_INSTRUCTION
from app.profile_store import InMemoryProfileStore


async def run_onboarding_bot(webrtc_connection: object, user_id: str, store: InMemoryProfileStore) -> None:
    settings = get_settings()
    if not settings.openai_api_key:
        logger.error("OPENAI_API_KEY is not configured; cannot start onboarding bot")
        return

    from pipecat.adapters.schemas.tools_schema import ToolsSchema
    from pipecat.frames.frames import LLMRunFrame
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.worker import PipelineParams, PipelineWorker
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
    from pipecat.services.openai.realtime.events import (
        AudioConfiguration,
        AudioInput,
        InputAudioNoiseReduction,
        InputAudioTranscription,
        SemanticTurnDetection,
        SessionProperties,
    )
    from pipecat.services.openai.realtime.llm import OpenAIRealtimeLLMService
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

        profile = store.upsert_profile(
            user_id,
            ProfilePatch(**patch_data),
        )
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

    llm_settings_kwargs = {
        "system_instruction": ONBOARDING_SYSTEM_INSTRUCTION,
        "session_properties": SessionProperties(
            audio=AudioConfiguration(
                input=AudioInput(
                    transcription=InputAudioTranscription(),
                    turn_detection=SemanticTurnDetection(),
                    noise_reduction=InputAudioNoiseReduction(type="near_field"),
                )
            )
        ),
    }
    if settings.openai_realtime_model:
        llm_settings_kwargs["model"] = settings.openai_realtime_model

    llm = OpenAIRealtimeLLMService(
        api_key=settings.openai_api_key,
        settings=OpenAIRealtimeLLMService.Settings(**llm_settings_kwargs),
    )
    llm.register_direct_function(save_profile)
    llm.register_direct_function(finish_onboarding)

    tools = ToolsSchema(standard_tools=[save_profile, finish_onboarding])
    context = LLMContext(tools=tools)
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(context)

    transport = SmallWebRTCTransport(
        params=TransportParams(audio_in_enabled=True, audio_out_enabled=True),
        webrtc_connection=webrtc_connection,
    )

    pipeline = Pipeline(
        [
            transport.input(),
            user_aggregator,
            llm,
            transport.output(),
            assistant_aggregator,
        ]
    )
    task = PipelineWorker(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        idle_timeout_secs=300,
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client) -> None:
        logger.info("Onboarding Call connected for user_id={}", user_id)
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client) -> None:
        logger.info("Onboarding Call disconnected for user_id={}", user_id)
        await task.cancel()

    runner = WorkerRunner(handle_sigint=False)
    await runner.run(task)
