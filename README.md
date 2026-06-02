# Voice Onboarding

AI voice onboarding for a mobile app. The User is already authenticated, starts an Onboarding Call, speaks with a Pipecat-powered AI guide, and lands on Home when the Profile is complete.

## Stack

- Backend: FastAPI + Pipecat + OpenAI Realtime
- Mobile: Expo React Native + Pipecat SmallWebRTC client
- Store: in-memory prototype store

## Local development

Start the backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 7860
```

Start the mobile app:

```bash
cd frontend
npm install
cp .env.example .env
npx expo run:ios
```

This uses native WebRTC modules, so Expo Go is not enough. Build a dev client with `expo run:ios` or `expo run:android`.
The backend needs `OPENAI_API_KEY` in `backend/.env` before a real AI voice call can connect.
For a physical device, set `EXPO_PUBLIC_API_BASE_URL` in `frontend/.env` and `PUBLIC_API_BASE_URL` in `backend/.env` to your computer's LAN URL, for example `http://192.168.1.20:7860`.

## First vertical slice

1. Expo calls `POST /api/onboarding/start` with a demo User ID.
2. FastAPI returns a Pipecat SmallWebRTC offer URL.
3. Expo connects the call to the Python Pipecat bot.
4. The bot calls `save_profile` as it learns facts.
5. The bot calls `finish_onboarding` when setup is done.
6. Expo polls `GET /api/onboarding/status/{user_id}` and switches to Home.

## Voice setup lab

The app can test multiple voice stacks from the same call UI:

| Setup | Stack | Required config |
| --- | --- | --- |
| `openai-realtime-mini` | OpenAI native speech-to-speech with `gpt-realtime-mini` | `OPENAI_API_KEY` |
| `openai-realtime-2` | OpenAI native speech-to-speech with `gpt-realtime-2` | `OPENAI_API_KEY` |
| `openai-cascaded` | OpenAI STT -> OpenAI text LLM -> OpenAI TTS | `OPENAI_API_KEY` |
| `deepgram-cartesia` | Deepgram STT -> OpenAI text LLM -> Cartesia TTS | `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`, `CARTESIA_API_KEY`, `CARTESIA_VOICE_ID` |

Use `GET /api/voice-setups` to see which setups are runnable on the current backend. The mobile UI shows the same availability status before starting a call.

## Production upgrades

- Replace the in-memory store with Postgres.
- Replace `demo-user-1` with the real authenticated User ID.
- Move from SmallWebRTC to Daily transport or Pipecat Cloud if you need managed global WebRTC.
- Add persistent transcript/audit storage only if the product or compliance requirements demand it.
