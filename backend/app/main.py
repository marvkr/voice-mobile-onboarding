from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.bot import run_onboarding_bot
from app.config import get_settings
from app.models import OnboardingStatus, StartOnboardingResponse
from app.profile_store import profile_store

settings = get_settings()
webrtc_request_handler: Any | None = None

app = FastAPI(title="Voice Onboarding API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _require_user_id(user_id: str | None) -> str:
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing x-user-id header or user_id query param")
    return user_id


def _require_voice_provider_configured() -> None:
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not configured on the backend",
        )


def _jsonable_answer(answer: Any) -> Any:
    if hasattr(answer, "model_dump"):
        return answer.model_dump()
    if hasattr(answer, "dict"):
        return answer.dict()
    return answer


def _get_webrtc_request_handler() -> Any:
    global webrtc_request_handler

    if webrtc_request_handler is None:
        try:
            from pipecat.transports.smallwebrtc.request_handler import SmallWebRTCRequestHandler
        except ImportError:  # Older Pipecat releases used a different module path.
            from pipecat.transports.network.small_webrtc import SmallWebRTCRequestHandler

        webrtc_request_handler = SmallWebRTCRequestHandler(ice_servers=settings.webrtc_ice_servers)
    return webrtc_request_handler


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/onboarding/start", response_model=StartOnboardingResponse)
async def start_onboarding(
    request: Request,
    x_user_id: str | None = Header(default=None),
) -> StartOnboardingResponse:
    _require_voice_provider_configured()
    user_id = _require_user_id(x_user_id)
    profile_store.ensure_profile(user_id)

    base_url = settings.public_api_base_url or str(request.base_url).rstrip("/")
    query = urlencode({"user_id": user_id})
    return StartOnboardingResponse(user_id=user_id, webrtc_url=f"{base_url}/api/offer?{query}")


@app.get("/api/onboarding/status/{user_id}", response_model=OnboardingStatus)
async def get_onboarding_status(user_id: str) -> OnboardingStatus:
    return profile_store.status(user_id)


@app.post("/api/onboarding/reset", response_model=OnboardingStatus)
async def reset_onboarding(x_user_id: str | None = Header(default=None)) -> OnboardingStatus:
    user_id = _require_user_id(x_user_id)
    profile_store.reset_profile(user_id)
    return profile_store.status(user_id)


@app.post("/api/offer")
async def offer(
    request: dict[str, Any],
    background_tasks: BackgroundTasks,
    user_id: str | None = Query(default=None),
    x_user_id: str | None = Header(default=None),
) -> Any:
    _require_voice_provider_configured()
    resolved_user_id = _require_user_id(user_id or x_user_id)

    try:
        from pipecat.transports.smallwebrtc.request_handler import SmallWebRTCRequest
    except ImportError:
        from pipecat.transports.network.small_webrtc import SmallWebRTCRequest

    if "sdp" not in request or "type" not in request:
        raise HTTPException(status_code=400, detail="Expected WebRTC offer with sdp and type")

    async def start_bot(connection: Any) -> None:
        @connection.event_handler("closed")
        async def on_closed(webrtc_connection) -> None:
            logger.info("WebRTC connection closed for user_id={}", resolved_user_id)

        background_tasks.add_task(run_onboarding_bot, connection, resolved_user_id, profile_store)

    answer = await _get_webrtc_request_handler().handle_web_request(
        SmallWebRTCRequest.from_dict(request),
        start_bot,
    )
    return _jsonable_answer(answer)


@app.patch("/api/offer")
async def offer_ice_candidate(
    request: dict[str, Any],
    user_id: str | None = Query(default=None),
    x_user_id: str | None = Header(default=None),
) -> dict[str, bool]:
    _require_voice_provider_configured()
    _require_user_id(user_id or x_user_id)

    try:
        from pipecat.transports.smallwebrtc.request_handler import IceCandidate, SmallWebRTCPatchRequest
    except ImportError:
        from pipecat.transports.network.small_webrtc import IceCandidate, SmallWebRTCPatchRequest

    if "pc_id" not in request or "candidates" not in request:
        raise HTTPException(status_code=400, detail="Expected pc_id and candidates")

    patch_request = SmallWebRTCPatchRequest(
        pc_id=request["pc_id"],
        candidates=[IceCandidate(**candidate) for candidate in request["candidates"]],
    )
    await _get_webrtc_request_handler().handle_patch_request(patch_request)
    return {"ok": True}
