# Voice onboarding backend

FastAPI hosts the app API and the Pipecat SmallWebRTC offer endpoint used by the Expo client.

## Run locally

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 7860
```

Set `OPENAI_API_KEY` before starting a real Onboarding Call.
If it is missing, `POST /api/onboarding/start` returns `503` with a clear setup error.

Leave `PUBLIC_API_BASE_URL` blank for local development so the backend returns WebRTC URLs based on the host the phone used to reach it (`localhost`, `10.0.2.2`, or your LAN IP).
For a physical device, set it to the same LAN URL used by `EXPO_PUBLIC_API_BASE_URL`, for example `http://192.168.1.20:7860`.

## Endpoints

- `POST /api/onboarding/start` with `x-user-id` returns a `webrtc_url`.
- `POST /api/offer?user_id=...` handles Pipecat SmallWebRTC offer/answer signaling.
- `GET /api/onboarding/status/{user_id}` returns whether the Onboarding Call has completed and the Profile captured so far.
- `POST /api/onboarding/reset` with `x-user-id` resets the in-memory prototype Profile.

The store is intentionally in-memory for the first vertical slice. Replace `app/profile_store.py` with Postgres once auth and the Profile schema stop moving.
