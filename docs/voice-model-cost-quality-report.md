# AI Voice Model Cost/Quality Report

Research date: June 2, 2026

Scope: voice-first onboarding for the existing Pipecat + FastAPI backend and Expo React Native mobile app. The user starts an Onboarding Call, speaks with an AI guide, the backend collects a Profile, then the app routes to Home.

Sources checked with Exa MCP and OpenAI docs MCP:

- [OpenAI Realtime cost guide](https://developers.openai.com/api/docs/guides/realtime-costs)
- [OpenAI gpt-realtime-2 model page](https://developers.openai.com/api/docs/models/gpt-realtime-2)
- [OpenAI gpt-realtime-mini model page](https://developers.openai.com/api/docs/models/gpt-realtime-mini)
- [OpenAI API pricing](https://openai.com/api/pricing/)
- [Google Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Google Gemini Enterprise Agent Platform pricing](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing)
- [Google Gemini Live session docs](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/live-api/start-manage-session)
- [Deepgram pricing](https://deepgram.com/pricing)
- [Cartesia pricing](https://cartesia.ai/pricing)
- [ElevenLabs API pricing](https://elevenlabs.io/pricing/api?price.section=speech_to_text)

## Executive Recommendation

Use OpenAI Realtime through Pipecat for the MVP, but change the default model to `gpt-realtime-mini` and keep `gpt-realtime-2` as the quality fallback.

That gives us the cleanest path because the app is already wired for Pipecat + OpenAI Realtime + WebRTC. The main risk is not integration. The main risk is cost control and whether the mini model reliably calls tools and completes the Profile.

Recommended operating model:

1. Default production model: `gpt-realtime-mini`.
2. Quality fallback: `gpt-realtime-2` for test runs, high-value users, or sessions where mini misses required Profile fields.
3. Hard call cap: 90 to 120 seconds.
4. Prompt cap: 2 to 3 questions, short spoken answers, finish as soon as Profile is good enough.
5. Instrument usage from OpenAI `response.done` events before any paid launch.
6. Revisit Gemini Live or a cascaded Pipecat stack if volume makes OpenAI Realtime cost meaningful.

If the question is "best quality for the money today," my ranking for this product is:

| Rank | Option | Why |
| --- | --- | --- |
| 1 | OpenAI `gpt-realtime-mini` via Pipecat | Best MVP tradeoff: same integration, much cheaper than full Realtime, good enough if tool calls pass evals. |
| 2 | Gemini Live API | Excellent raw audio pricing and strong native audio path, but it means provider/integration migration. |
| 3 | Pipecat cascaded stack: Deepgram STT + cheaper LLM + Cartesia or ElevenLabs TTS | Best long-term cost control, but more moving parts and more latency tuning. |
| 4 | OpenAI `gpt-realtime-2` | Highest quality/reliability for realtime tool-calling, but expensive enough that it should not be the default for simple onboarding. |
| 5 | Deepgram/Cartesia/ElevenLabs managed agent products | Useful if we want less custom backend work, but they shift orchestration lock-in to another vendor. |

## Current Architecture Fit

The current prototype already uses:

- Backend: FastAPI + Pipecat + OpenAI Realtime.
- Mobile: Expo React Native + Pipecat SmallWebRTC client.
- Product flow: authenticated User starts an Onboarding Call, the bot collects a Profile, then calls `finish_onboarding`.

That means the cheapest engineering path is to tune the model and prompt first, not replace the whole voice architecture.

The biggest cost lever is call shape:

- Keep the Onboarding Call short.
- Avoid long assistant monologues.
- Save Profile facts early.
- Finish quickly once enough information is captured.
- Do not let conversation history grow for no product reason.

## OpenAI Realtime

### `gpt-realtime-2`

OpenAI describes `gpt-realtime-2` as its most capable realtime voice model, with stronger instruction following and more reliable tool use for complex voice-agent workflows.

Official pricing found:

| Modality | Input | Cached input | Output |
| --- | ---: | ---: | ---: |
| Text | $4.00 / 1M tokens | $0.40 / 1M tokens | $24.00 / 1M tokens |
| Audio | $32.00 / 1M tokens | $0.40 / 1M tokens | $64.00 / 1M tokens |
| Image | $5.00 / 1M tokens | $0.50 / 1M tokens | N/A |

Important billing mechanics from OpenAI:

- Realtime costs accrue when a Response is created.
- User audio is about 1 token per 100 ms.
- Assistant audio is about 1 token per 50 ms.
- The entire conversation is sent for each Response, so later turns can cost more.
- Prompt caching can reduce repeated input cost, but it is not something to rely on blindly.
- Input transcription, if enabled, is billed separately.
- Usage can be read from `response.done`.

Back-of-envelope audio-only cost for `gpt-realtime-2`:

| Scenario | Raw audio token estimate | Audio-only cost |
| --- | ---: | ---: |
| 60s call: 30s user, 30s assistant | 300 input audio tokens + 600 output audio tokens | ~$0.048 |
| 120s call: 45s user, 75s assistant | 450 input audio tokens + 1,500 output audio tokens | ~$0.110 |

Those numbers exclude text tokens, system instructions, tool definitions, repeated conversation context, input transcription, and failed/extra turns. Real sessions should be measured, not estimated from duration alone.

Verdict: best quality and best tool reliability, but too expensive to make the default for a simple onboarding call unless mini fails quality tests.

### `gpt-realtime-mini`

OpenAI describes `gpt-realtime-mini` as a cost-efficient version of GPT Realtime. The OpenAI cost guide says mini models are significantly cheaper, with the tradeoff usually being weaker instruction following and function calling.

Official pricing found in fetched model docs:

| Modality | Input | Cached input | Output |
| --- | ---: | ---: | ---: |
| Text | $0.60 / 1M tokens | $0.06 / 1M tokens | $2.40 / 1M tokens |

The fetched public docs clearly list text token pricing for `gpt-realtime-mini`, but did not expose a clean official audio-token rate in the fetched content. Before using mini in a finance forecast, verify the current audio rate in the OpenAI pricing page/dashboard.

Verdict: best default for our MVP if it passes a small quality eval. It keeps the current Pipecat integration and should reduce cost materially.

Recommended eval gate:

- Run 20 to 30 scripted onboarding calls on `gpt-realtime-mini`.
- Run the same calls on `gpt-realtime-2`.
- Pass criteria: mini captures required Profile fields at >=95% of the full model's completion rate.
- Pass criteria: mini calls `save_profile` and `finish_onboarding` reliably.
- Pass criteria: median call duration stays under 90 seconds.
- If mini fails, keep `gpt-realtime-2` as default temporarily and tighten prompt/tool schema.

## Google Gemini Live

Relevant models:

- `gemini-3.1-flash-live-preview` on the Gemini API pricing page.
- `gemini-live-2.5-flash-native-audio` in Google Cloud Live API docs.

Official pricing found:

| Model family | Input audio | Output audio | Input text | Output text |
| --- | ---: | ---: | ---: | ---: |
| Gemini Live Flash | $3.00 / 1M audio tokens, shown as about $0.005/min | $12.00 / 1M audio tokens, shown as about $0.018/min | $0.50 to $0.75 / 1M tokens depending model/page | $2.00 to $4.50 / 1M tokens depending model/page |

Official token mechanics:

- Google docs state audio is 25 tokens per second.
- Live sessions have context window behavior; accumulated audio/text history can be part of later turns.
- Google pricing explains that Live API can charge per turn for all tokens in the session context window.
- Audio-only sessions have practical limits without context compression, and WebSocket connections also have lifecycle limits.

Back-of-envelope raw audio cost:

| Scenario | Raw audio estimate | Raw audio cost |
| --- | ---: | ---: |
| 60s call: 30s user, 30s assistant | ~750 input tokens + ~750 output tokens | ~$0.0115 |
| 120s call: 45s user, 75s assistant | ~1,125 input tokens + ~1,875 output tokens | ~$0.028 |

Those estimates ignore context re-billing. For short onboarding, Gemini Live could be very cost attractive. For longer, multi-turn calls, measure actual bills because session context billing can change the shape.

Verdict: very strong cost candidate, especially if scale matters. Not the first move because it means changing provider integration after we already have OpenAI Realtime running through Pipecat.

## Cascaded Pipecat Stack

A cascaded stack means:

1. STT turns user speech into text.
2. A text LLM decides what to say and which tool to call.
3. TTS generates the assistant voice.

This gives more control and more provider optionality than a native speech-to-speech model, but adds latency and orchestration complexity.

### Deepgram

Deepgram official pricing highlights:

| Product | Price |
| --- | ---: |
| Nova-3 Monolingual STT streaming | $0.0048/min pay-as-you-go |
| Nova-3 Multilingual STT streaming | $0.0058/min pay-as-you-go |
| Flux English conversational STT | $0.0065/min pay-as-you-go |
| Aura-1 TTS | $0.0150 / 1K characters |
| Aura-2 TTS | $0.030 / 1K characters |
| Voice Agent API Standard | $0.075/min |
| Voice Agent API Custom BYO LLM + TTS | $0.050/min |

Deepgram is especially attractive as the STT layer. For our app, it is a strong option if we move away from native speech-to-speech and want best-in-class transcription with low per-minute cost.

### Cartesia

Cartesia official pricing highlights:

| Product | Price |
| --- | ---: |
| Sonic-3.5 TTS | Included via monthly credits; Pro shows about 133 TTS minutes/month for $4/mo |
| Scale TTS | About 10,667 included TTS minutes/month for $239/mo |
| Line voice agents | $0.06/min call duration |
| Cartesia phone number telephony | +$0.014/min |

Cartesia is attractive for low-latency TTS and simple agent minutes. The main caution is that its agent pricing separates call duration from plan credits and says some LLM usage is free for a limited time, so do not model that as permanent.

### ElevenLabs

ElevenLabs official pricing highlights:

| Product | Price |
| --- | ---: |
| Flash/Turbo TTS | $0.05 / 1K characters |
| Multilingual v2/v3 TTS | $0.10 / 1K characters |
| Scribe STT | $0.22/hour |
| Scribe v2 Realtime STT | $0.39/hour |
| Speech Engine agent API | $0.08/min |

ElevenLabs is usually a voice-quality and voice-catalog pick more than a cheapest-cost pick. It is worth testing if the brand experience depends heavily on a premium voice.

Verdict for cascaded stack: best long-term optimization path, but not the first MVP move. Use it when real usage data says OpenAI Realtime cost is too high.

## Provider Comparison

| Option | Quality | Cost profile | Integration fit | Lock-in | Recommendation |
| --- | --- | --- | --- | --- | --- |
| OpenAI `gpt-realtime-mini` | Likely good enough for short onboarding; weaker than full model on tool reliability | Lower-cost mini model, exact audio rates should be verified | Excellent, same path we already built | Medium | Default MVP candidate |
| OpenAI `gpt-realtime-2` | Best realtime quality and tool reliability | Expensive audio output; assistant speech costs more than user speech | Excellent, same path we already built | Medium | Fallback and benchmark |
| Gemini Live | Strong native audio candidate; good multilingual story | Very attractive raw audio pricing, but context billing matters | Medium, requires provider adapter/migration | Medium | POC after MVP or before high-volume launch |
| Deepgram STT + LLM + TTS | High control; STT quality is strong | Very tunable; STT is cheap, TTS/LLM vary | Medium, more moving parts in Pipecat | Low to medium | Best scale optimization path |
| Cartesia Line | Strong latency/cost posture for voice agents | $0.06/min agent duration plus telephony/credits | Medium, managed agent path | Medium to high | Test if speed and cost beat custom stack |
| ElevenLabs Speech Engine | Premium voice/catalog angle | $0.08/min agent API or higher TTS char rates | Medium, managed agent path | Medium to high | Test if voice quality is the differentiator |
| Deepgram Voice Agent API | Simple bundled voice-agent layer | $0.050 to $0.075/min depending BYO config | Medium, replaces some Pipecat custom control | Medium to high | Useful managed alternative |

## Practical Cost Controls For Our App

Do these before worrying about a full architecture change:

1. Set `OPENAI_REALTIME_MODEL=gpt-realtime-mini` explicitly.
2. Add `MAX_ONBOARDING_CALL_SECONDS=120`.
3. Update the system prompt to say: "Ask at most 3 questions. Keep replies under 10 seconds. Finish as soon as enough Profile data is collected."
4. Capture model usage from `response.done`.
5. Store per-session cost telemetry with user ID, model, call duration, input audio tokens, output audio tokens, text tokens, tool-call success, and completion status.
6. Add a backend rate limit per User for Onboarding Calls.
7. Add an OpenAI project budget alert before external testers use the app.
8. Keep `gpt-realtime-2` available as an environment-controlled fallback.

## When To Revisit Architecture

Stay on OpenAI Realtime if:

- We are still proving product value.
- Monthly onboarding volume is low or moderate.
- The call is usually under 90 seconds.
- The team cares more about speed of implementation than shaving cents.

Run a Gemini Live POC if:

- We expect thousands to tens of thousands of onboardings per month.
- Raw voice cost becomes a real line item.
- Spanish/multilingual behavior becomes important.
- We can afford a provider adapter without slowing the product.

Run a cascaded Pipecat POC if:

- We need provider portability.
- We want best-in-class STT, cheaper LLM routing, and carefully selected TTS.
- We need to swap TTS voices independently of reasoning quality.
- We can tolerate additional latency engineering.

## Final Decision

For this app, ship the MVP with Pipecat + OpenAI Realtime, but default to `gpt-realtime-mini` and measure it against `gpt-realtime-2`.

Do not prematurely rebuild the backend around Gemini or a cascaded STT/LLM/TTS stack. The cheapest code is the code we do not rewrite yet. But do add cost telemetry immediately, because without usage data we are just arguing with vibes in a spreadsheet costume.
