import { Platform } from 'react-native';

export const USER_ID = 'demo-user-1';

export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ??
  (Platform.OS === 'android' ? 'http://10.0.2.2:7860' : 'http://localhost:7860');

export type Profile = {
  user_id: string;
  display_name: string | null;
  primary_goal: string | null;
  interests: string[];
  communication_style: string | null;
  language: string | null;
  notes: string | null;
  completed: boolean;
};

export type OnboardingStatus = {
  user_id: string;
  completed: boolean;
  next_screen: 'home' | null;
  profile: Profile;
};

export type VoiceSetupId =
  | 'openai-realtime-mini'
  | 'openai-realtime-2'
  | 'openai-cascaded'
  | 'deepgram-cartesia';

export type VoiceSetup = {
  id: VoiceSetupId;
  label: string;
  stack: string;
  available: boolean;
  required_env: string[];
  missing_env: string[];
  missing_dependencies: string[];
  cost_note: string;
  quality_note: string;
};

export type StartOnboardingResult = {
  user_id: string;
  webrtc_url: string;
  voice_setup: VoiceSetup;
};

async function errorMessage(response: Response, fallback: string) {
  try {
    const body: unknown = await response.json();
    if (body && typeof body === 'object' && 'detail' in body && typeof body.detail === 'string') {
      return body.detail;
    }
  } catch {
    // Some upstream errors are not JSON; keep the call-site fallback readable.
  }

  return `${fallback}: ${response.status}`;
}

export async function getVoiceSetups(): Promise<VoiceSetup[]> {
  const response = await fetch(`${API_BASE_URL}/api/voice-setups`);

  if (!response.ok) {
    throw new Error(await errorMessage(response, 'Could not read voice setups'));
  }

  return response.json();
}

export async function startOnboarding(userId: string, voiceSetup: VoiceSetupId): Promise<StartOnboardingResult> {
  const response = await fetch(`${API_BASE_URL}/api/onboarding/start`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'x-user-id': userId,
    },
    body: JSON.stringify({ voice_setup: voiceSetup }),
  });

  if (!response.ok) {
    throw new Error(await errorMessage(response, 'Could not start onboarding'));
  }

  return response.json();
}

export async function getOnboardingStatus(userId: string): Promise<OnboardingStatus> {
  const response = await fetch(`${API_BASE_URL}/api/onboarding/status/${encodeURIComponent(userId)}`);

  if (!response.ok) {
    throw new Error(await errorMessage(response, 'Could not read onboarding status'));
  }

  return response.json();
}

export async function resetOnboarding(userId: string): Promise<OnboardingStatus> {
  const response = await fetch(`${API_BASE_URL}/api/onboarding/reset`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'x-user-id': userId,
    },
  });

  if (!response.ok) {
    throw new Error(await errorMessage(response, 'Could not reset onboarding'));
  }

  return response.json();
}
