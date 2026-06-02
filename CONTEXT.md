# Voice Onboarding

A voice-first onboarding for a mobile app: a new user holds a spoken conversation with an AI that both collects a profile and verbally guides them, then drops them into the app.

## Language

**Onboarding Call**:
The single spoken conversation a new user has with the AI to get set up. Call-style UI; voice only. Ends by sending the user to the home screen.
_Avoid_: session, chat, interview

**User**:
The authenticated account (email/Apple/Google). Exists *before* the Onboarding Call. Identity the Profile attaches to.
_Avoid_: account, customer

**Profile**:
The structured information captured from a User during an Onboarding Call, used to personalize the app afterward. Distinct from the User: the User is the login identity; the Profile is the personalization data.
_Avoid_: account, user data

**Collect**:
The intent within an Onboarding Call where the AI asks questions and builds the Profile.

**Guide**:
The intent within an Onboarding Call where the AI verbally explains/orients the user. Branches based on what was collected. Purely spoken — no on-screen control.
_Avoid_: tour, walkthrough (pick one — "Guide")

## Relationships

- An **Onboarding Call** produces exactly one **Profile**
- An **Onboarding Call** interleaves two intents: **Collect** and **Guide**

## Flagged ambiguities

- "Spanish" appeared in an early voice note — unresolved whether multi-language support is in scope. _Pending._
