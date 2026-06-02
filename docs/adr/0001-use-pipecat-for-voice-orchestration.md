# Use Pipecat for voice orchestration

We will build the voice onboarding stack on Pipecat instead of LiveKit Agents because the project values vendor-neutral orchestration and swappable realtime transports over a more turnkey single-stack platform. Pipecat keeps the Python agent, realtime model choice, and mobile transport boundaries explicit, while still supporting an Expo client path through SmallWebRTC for local development and Daily/Pipecat Cloud when production scale needs it.

