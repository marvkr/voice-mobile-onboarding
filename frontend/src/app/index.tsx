import 'react-native-get-random-values';

import { PipecatClient, RTVIEvent, type Transport } from '@pipecat-ai/client-js';
import { DailyMediaManager } from '@pipecat-ai/react-native-daily-media-manager';
import { RNSmallWebRTCTransport } from '@pipecat-ai/react-native-small-webrtc-transport';
import { useEffect, useState } from 'react';
import {
  Animated,
  Easing,
  Platform,
  Pressable,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import {
  getOnboardingStatus,
  getVoiceSetups,
  resetOnboarding,
  startOnboarding,
  USER_ID,
  type Profile,
  type VoiceSetup,
  type VoiceSetupId,
} from '@/api';

type Message = {
  role: 'assistant' | 'user';
  text: string;
};

type Screen = 'call' | 'home';

function createClient() {
  const transport = new RNSmallWebRTCTransport({
    mediaManager: new DailyMediaManager(),
  }) as unknown as Transport;

  return new PipecatClient({
    transport,
    enableMic: true,
    enableCam: false,
  });
}

export default function VoiceOnboardingScreen() {
  const [client] = useState(() => createClient());
  const [pulse] = useState(() => new Animated.Value(0));
  const [screen, setScreen] = useState<Screen>('call');
  const [transportState, setTransportState] = useState('disconnected');
  const [messages, setMessages] = useState<Message[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [voiceSetups, setVoiceSetups] = useState<VoiceSetup[]>([]);
  const [selectedVoiceSetupId, setSelectedVoiceSetupId] = useState<VoiceSetupId>('openai-realtime-mini');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const animation = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: 1,
          duration: 1300,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: true,
        }),
        Animated.timing(pulse, {
          toValue: 0,
          duration: 900,
          easing: Easing.in(Easing.cubic),
          useNativeDriver: true,
        }),
      ])
    );

    animation.start();
    return () => animation.stop();
  }, [pulse]);

  useEffect(() => {
    let mounted = true;

    getVoiceSetups()
      .then((setups) => {
        if (!mounted) {
          return;
        }
        setVoiceSetups(setups);
      })
      .catch((caught) => {
        if (mounted) {
          setError(caught instanceof Error ? caught.message : 'Could not load voice setups');
        }
      });

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    const onStateChange = (state: string) => setTransportState(state);
    const onBotOutput = (data: { text?: string; aggregated_by?: string }) => {
      if (data.text && (!data.aggregated_by || data.aggregated_by === 'sentence')) {
        setMessages((current) => [...current, { role: 'assistant', text: data.text ?? '' }]);
      }
    };
    const onUserTranscript = (data: { text?: string; final?: boolean }) => {
      if (data.final && data.text) {
        setMessages((current) => [...current, { role: 'user', text: data.text ?? '' }]);
      }
    };
    const onError = (event: unknown) => setError(event instanceof Error ? event.message : 'Voice call error');

    client.on(RTVIEvent.TransportStateChanged, onStateChange);
    client.on(RTVIEvent.BotOutput, onBotOutput);
    client.on(RTVIEvent.UserTranscript, onUserTranscript);
    client.on(RTVIEvent.Error, onError);

    return () => {
      client.off(RTVIEvent.TransportStateChanged, onStateChange);
      client.off(RTVIEvent.BotOutput, onBotOutput);
      client.off(RTVIEvent.UserTranscript, onUserTranscript);
      client.off(RTVIEvent.Error, onError);
    };
  }, [client]);

  useEffect(() => {
    if (screen !== 'call' || transportState === 'disconnected') {
      return;
    }

    const interval = setInterval(() => {
      getOnboardingStatus(USER_ID)
        .then((status) => {
          setProfile(status.profile);
          if (status.completed && status.next_screen === 'home') {
            client.disconnect();
            setScreen('home');
          }
        })
        .catch(() => {
          // A missed status poll should not interrupt the live call.
        });
    }, 1500);

    return () => clearInterval(interval);
  }, [client, screen, transportState]);

  const isConnecting = ['authenticating', 'connecting', 'connected'].includes(transportState);
  const isReady = transportState === 'ready';
  const callInProgress = isConnecting || isReady;
  const selectedVoiceSetup = voiceSetups.find((setup) => setup.id === selectedVoiceSetupId) ?? voiceSetups[0] ?? null;

  async function startCall(voiceSetupId = selectedVoiceSetupId) {
    setError(null);
    setMessages([]);
    setSelectedVoiceSetupId(voiceSetupId);

    const voiceSetup = voiceSetups.find((setup) => setup.id === voiceSetupId) ?? null;

    if (callInProgress) {
      return;
    }
    if (!voiceSetup) {
      setError('Voice setups are still loading. Try again in a moment.');
      return;
    }
    if (!voiceSetup.available) {
      setError(`${voiceSetup.label} is not configured. ${unavailableReason(voiceSetup)}`);
      return;
    }

    try {
      const { webrtc_url: webrtcUrl } = await startOnboarding(USER_ID, voiceSetup.id);
      await client.connect({ webrtcUrl });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not start voice onboarding');
    }
  }

  async function endCall() {
    await client.disconnect();
    setTransportState('disconnected');
  }

  async function resetCall() {
    setError(null);
    setMessages([]);
    setProfile(null);
    setTransportState('disconnected');
    try {
      await resetOnboarding(USER_ID);
    } catch {
      // Reset is a prototype convenience; the next start attempt can still surface backend errors.
    }
    setScreen('call');
  }

  if (screen === 'home') {
    return <HomeScreen profile={profile} onReset={resetCall} />;
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="light-content" />
      <View style={styles.backgroundOrbTop} />
      <View style={styles.backgroundOrbBottom} />

      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.kicker}>Voice setup</Text>
          <Text style={styles.title}>Talk your way into the app.</Text>
          <Text style={styles.subtitle}>
            A short AI call collects your preferences, then sends you to Home when setup is done.
          </Text>
        </View>

        <SetupSelector
          disabled={callInProgress}
          onStart={startCall}
          selectedId={selectedVoiceSetup?.id ?? selectedVoiceSetupId}
          setups={voiceSetups}
        />

        <View style={styles.callCard}>
          <Animated.View
            style={[
              styles.pulseRing,
              {
                opacity: pulse.interpolate({ inputRange: [0, 1], outputRange: [0.35, 0.08] }),
                transform: [{ scale: pulse.interpolate({ inputRange: [0, 1], outputRange: [0.86, 1.18] }) }],
              },
            ]}
          />
          <Text style={styles.setupBadge}>{selectedVoiceSetup?.label ?? 'Loading setups'}</Text>
          <View style={styles.micCircle}>
            <Text style={styles.micGlyph}>voice</Text>
          </View>
          <Text style={styles.stateLabel}>{isReady ? 'Listening now' : humanizeState(transportState)}</Text>
          <Text style={styles.stateHint}>
            {isReady
              ? 'Speak naturally. Interruptions are fine.'
              : isConnecting
                ? `Connecting with ${selectedVoiceSetup?.label ?? 'selected setup'}.`
                : 'Tap a setup card above to start that exact experience.'}
          </Text>

          <View style={styles.actions}>
            {callInProgress ? (
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={isReady ? 'End onboarding call' : 'Connecting onboarding call'}
                disabled={isConnecting}
                onPress={endCall}
                style={({ pressed }) => [
                  styles.primaryButton,
                  isConnecting && styles.buttonDisabled,
                  pressed && isReady && styles.buttonPressed,
                ]}>
                <Text style={styles.primaryButtonText}>{isReady ? 'End call' : 'Connecting...'}</Text>
              </Pressable>
            ) : (
              <Text style={styles.tapHint}>Choose a setup to launch the call.</Text>
            )}
          </View>
        </View>

        {error ? <Text style={styles.errorText}>{error}</Text> : null}

        <ScrollView contentContainerStyle={styles.transcript} showsVerticalScrollIndicator={false}>
          {messages.length === 0 ? (
            <Text style={styles.emptyTranscript}>Transcript appears here once the call starts.</Text>
          ) : (
            messages.slice(-6).map((message, index) => (
              <View
                key={`${message.role}-${index}-${message.text}`}
                style={[styles.messageBubble, message.role === 'user' ? styles.userBubble : styles.assistantBubble]}>
                <Text style={styles.messageRole}>{message.role === 'user' ? 'You' : 'Guide'}</Text>
                <Text style={styles.messageText}>{message.text}</Text>
              </View>
            ))
          )}
        </ScrollView>
      </View>
    </SafeAreaView>
  );
}

function SetupSelector({
  disabled,
  onStart,
  selectedId,
  setups,
}: {
  disabled: boolean;
  onStart: (setupId: VoiceSetupId) => void;
  selectedId: VoiceSetupId;
  setups: VoiceSetup[];
}) {
  if (setups.length === 0) {
    return (
      <View style={styles.setupSection}>
        <Text style={styles.setupTitle}>Voice setup lab</Text>
        <Text style={styles.setupCaption}>Loading selectable voice stacks from the backend.</Text>
      </View>
    );
  }

  return (
    <View style={styles.setupSection}>
      <View style={styles.setupHeaderRow}>
        <Text style={styles.setupTitle}>Voice setup lab</Text>
        <Text style={styles.setupCaption}>Tap a card to start a call with that exact stack.</Text>
      </View>
      <ScrollView
        contentContainerStyle={styles.setupList}
        horizontal
        showsHorizontalScrollIndicator={false}>
        {setups.map((setup) => {
          const selected = setup.id === selectedId;
          return (
            <Pressable
              accessibilityLabel={
                setup.available ? `Start onboarding with ${setup.label}` : `${setup.label} is not configured`
              }
              accessibilityRole="button"
              accessibilityState={{ selected, disabled }}
              disabled={disabled}
              key={setup.id}
              onPress={() => onStart(setup.id)}
              style={({ pressed }) => [
                styles.setupCard,
                selected && styles.setupCardActive,
                !setup.available && styles.setupCardUnavailable,
                pressed && !disabled && styles.buttonPressed,
              ]}>
              <View style={styles.setupCardTopRow}>
                <Text style={styles.setupLabel}>{setup.label}</Text>
                <View style={[styles.setupPill, setup.available ? styles.setupPillReady : styles.setupPillBlocked]}>
                  <Text style={styles.setupPillText}>{setup.available ? 'Ready' : 'Needs config'}</Text>
                </View>
              </View>
              <Text style={styles.setupStack}>{setup.stack}</Text>
              <Text style={styles.setupNote}>{setup.cost_note}</Text>
              {!setup.available ? <Text style={styles.setupUnavailableText}>{unavailableReason(setup)}</Text> : null}
              <Text style={[styles.setupAction, setup.available ? styles.setupActionReady : styles.setupActionBlocked]}>
                {disabled
                  ? selected
                    ? 'Running this setup'
                    : 'Locked during call'
                  : setup.available
                    ? 'Tap to test this setup'
                    : 'Tap to see what is missing'}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}

function HomeScreen({ profile, onReset }: { profile: Profile | null; onReset: () => void }) {
  return (
    <SafeAreaView style={styles.homeSafeArea}>
      <StatusBar barStyle="dark-content" />
      <View style={styles.homeContainer}>
        <Text style={styles.homeKicker}>Home</Text>
        <Text style={styles.homeTitle}>You are set up.</Text>
        <Text style={styles.homeSubtitle}>
          {profile?.display_name ? `Welcome, ${profile.display_name}.` : 'Welcome.'} Your app can now personalize around
          {profile?.primary_goal ? ` ${profile.primary_goal}` : ' the goals you shared'}.
        </Text>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Return to voice onboarding"
          onPress={onReset}
          style={styles.secondaryButton}>
          <Text style={styles.secondaryButtonText}>Run onboarding again</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

function unavailableReason(setup: VoiceSetup) {
  const missing = [...setup.missing_env, ...setup.missing_dependencies];
  if (missing.length === 0) {
    return 'Backend setup is incomplete.';
  }
  return `Missing ${missing.join(', ')}.`;
}

function humanizeState(state: string) {
  if (state === 'disconnected') {
    return 'Ready when you are';
  }
  return state
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

const ink = 'hsl(48, 32%, 8%)';
const cream = 'hsl(43, 77%, 92%)';
const ember = 'hsl(24, 88%, 55%)';
const moss = 'hsl(137, 28%, 24%)';

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: ink,
  },
  backgroundOrbTop: {
    position: 'absolute',
    top: -120,
    right: -80,
    width: 260,
    height: 260,
    borderRadius: 130,
    backgroundColor: 'hsla(24, 88%, 55%, 0.38)',
  },
  backgroundOrbBottom: {
    position: 'absolute',
    bottom: -160,
    left: -90,
    width: 300,
    height: 300,
    borderRadius: 150,
    backgroundColor: 'hsla(137, 28%, 34%, 0.58)',
  },
  container: {
    flex: 1,
    paddingHorizontal: 24,
    paddingTop: Platform.OS === 'android' ? 56 : 24,
    paddingBottom: 24,
    gap: 24,
  },
  header: {
    gap: 12,
  },
  kicker: {
    color: 'hsl(43, 77%, 72%)',
    fontFamily: Platform.select({ ios: 'Avenir Next', android: 'sans-serif-medium' }),
    fontSize: 13,
    fontWeight: '700',
    letterSpacing: 1.8,
    textTransform: 'uppercase',
  },
  title: {
    maxWidth: 330,
    color: cream,
    fontFamily: Platform.select({ ios: 'Georgia', android: 'serif' }),
    fontSize: 42,
    fontWeight: '700',
    letterSpacing: -1.4,
    lineHeight: 46,
  },
  subtitle: {
    maxWidth: 340,
    color: 'hsl(43, 42%, 76%)',
    fontFamily: Platform.select({ ios: 'Avenir Next', android: 'sans-serif' }),
    fontSize: 16,
    lineHeight: 24,
  },
  setupSection: {
    gap: 12,
  },
  setupHeaderRow: {
    gap: 4,
  },
  setupTitle: {
    color: cream,
    fontFamily: Platform.select({ ios: 'Avenir Next', android: 'sans-serif-medium' }),
    fontSize: 16,
    fontWeight: '800',
  },
  setupCaption: {
    color: 'hsl(43, 34%, 70%)',
    fontFamily: Platform.select({ ios: 'Avenir Next', android: 'sans-serif' }),
    fontSize: 13,
    lineHeight: 18,
  },
  setupList: {
    gap: 12,
    paddingRight: 24,
  },
  setupCard: {
    width: 246,
    gap: 10,
    borderWidth: 1,
    borderColor: 'hsla(43, 77%, 82%, 0.16)',
    borderRadius: 24,
    backgroundColor: 'hsla(43, 77%, 92%, 0.08)',
    padding: 16,
  },
  setupCardActive: {
    borderColor: ember,
    backgroundColor: 'hsla(24, 88%, 55%, 0.18)',
  },
  setupCardUnavailable: {
    opacity: 0.72,
  },
  setupCardTopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  setupLabel: {
    flex: 1,
    color: cream,
    fontFamily: Platform.select({ ios: 'Avenir Next', android: 'sans-serif-medium' }),
    fontSize: 15,
    fontWeight: '800',
  },
  setupPill: {
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 5,
  },
  setupPillReady: {
    backgroundColor: 'hsla(137, 36%, 42%, 0.82)',
  },
  setupPillBlocked: {
    backgroundColor: 'hsla(6, 72%, 46%, 0.78)',
  },
  setupPillText: {
    color: cream,
    fontFamily: Platform.select({ ios: 'Avenir Next', android: 'sans-serif-medium' }),
    fontSize: 10,
    fontWeight: '800',
    textTransform: 'uppercase',
  },
  setupStack: {
    color: 'hsl(43, 52%, 82%)',
    fontFamily: Platform.select({ ios: 'Avenir Next', android: 'sans-serif-medium' }),
    fontSize: 12,
    fontWeight: '700',
    lineHeight: 17,
  },
  setupNote: {
    color: 'hsl(43, 34%, 70%)',
    fontFamily: Platform.select({ ios: 'Avenir Next', android: 'sans-serif' }),
    fontSize: 12,
    lineHeight: 17,
  },
  setupUnavailableText: {
    color: 'hsl(6, 92%, 76%)',
    fontFamily: Platform.select({ ios: 'Avenir Next', android: 'sans-serif-medium' }),
    fontSize: 12,
    fontWeight: '700',
    lineHeight: 17,
  },
  setupAction: {
    marginTop: 2,
    fontFamily: Platform.select({ ios: 'Avenir Next', android: 'sans-serif-medium' }),
    fontSize: 12,
    fontWeight: '900',
    letterSpacing: 0.2,
  },
  setupActionReady: {
    color: 'hsl(43, 87%, 84%)',
  },
  setupActionBlocked: {
    color: 'hsl(6, 92%, 80%)',
  },
  callCard: {
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 300,
    padding: 32,
    borderWidth: 1,
    borderColor: 'hsla(43, 77%, 82%, 0.18)',
    borderRadius: 36,
    backgroundColor: 'hsla(43, 77%, 92%, 0.08)',
    overflow: 'hidden',
  },
  setupBadge: {
    marginBottom: 18,
    color: 'hsl(43, 77%, 78%)',
    fontFamily: Platform.select({ ios: 'Avenir Next', android: 'sans-serif-medium' }),
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  pulseRing: {
    position: 'absolute',
    width: 210,
    height: 210,
    borderRadius: 105,
    backgroundColor: ember,
  },
  micCircle: {
    width: 132,
    height: 132,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 66,
    backgroundColor: cream,
    shadowColor: ember,
    shadowOffset: { width: 0, height: 20 },
    shadowOpacity: 0.32,
    shadowRadius: 30,
    elevation: 8,
  },
  micGlyph: {
    color: ink,
    fontFamily: Platform.select({ ios: 'Avenir Next', android: 'sans-serif-medium' }),
    fontSize: 18,
    fontWeight: '800',
    letterSpacing: 0.4,
  },
  stateLabel: {
    marginTop: 24,
    color: cream,
    fontFamily: Platform.select({ ios: 'Avenir Next', android: 'sans-serif-medium' }),
    fontSize: 22,
    fontWeight: '800',
  },
  stateHint: {
    marginTop: 8,
    color: 'hsl(43, 42%, 74%)',
    fontFamily: Platform.select({ ios: 'Avenir Next', android: 'sans-serif' }),
    fontSize: 14,
    lineHeight: 20,
    textAlign: 'center',
  },
  actions: {
    marginTop: 24,
  },
  tapHint: {
    color: 'hsl(43, 38%, 72%)',
    fontFamily: Platform.select({ ios: 'Avenir Next', android: 'sans-serif-medium' }),
    fontSize: 13,
    fontWeight: '700',
    textAlign: 'center',
  },
  primaryButton: {
    minWidth: 178,
    alignItems: 'center',
    borderRadius: 999,
    backgroundColor: ember,
    paddingHorizontal: 28,
    paddingVertical: 16,
  },
  buttonDisabled: {
    opacity: 0.58,
  },
  buttonPressed: {
    transform: [{ scale: 0.98 }],
  },
  primaryButtonText: {
    color: ink,
    fontFamily: Platform.select({ ios: 'Avenir Next', android: 'sans-serif-medium' }),
    fontSize: 16,
    fontWeight: '800',
  },
  errorText: {
    color: 'hsl(6, 92%, 76%)',
    fontFamily: Platform.select({ ios: 'Avenir Next', android: 'sans-serif' }),
    fontSize: 14,
    lineHeight: 20,
  },
  transcript: {
    gap: 12,
    paddingBottom: 24,
  },
  emptyTranscript: {
    color: 'hsl(43, 28%, 63%)',
    fontFamily: Platform.select({ ios: 'Avenir Next', android: 'sans-serif' }),
    fontSize: 14,
  },
  messageBubble: {
    maxWidth: '86%',
    gap: 4,
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  assistantBubble: {
    alignSelf: 'flex-start',
    backgroundColor: 'hsla(43, 77%, 92%, 0.14)',
  },
  userBubble: {
    alignSelf: 'flex-end',
    backgroundColor: 'hsla(137, 28%, 44%, 0.72)',
  },
  messageRole: {
    color: 'hsl(43, 56%, 77%)',
    fontFamily: Platform.select({ ios: 'Avenir Next', android: 'sans-serif-medium' }),
    fontSize: 12,
    fontWeight: '800',
    textTransform: 'uppercase',
  },
  messageText: {
    color: cream,
    fontFamily: Platform.select({ ios: 'Avenir Next', android: 'sans-serif' }),
    fontSize: 15,
    lineHeight: 22,
  },
  homeSafeArea: {
    flex: 1,
    backgroundColor: cream,
  },
  homeContainer: {
    flex: 1,
    justifyContent: 'center',
    padding: 32,
    gap: 16,
  },
  homeKicker: {
    color: moss,
    fontFamily: Platform.select({ ios: 'Avenir Next', android: 'sans-serif-medium' }),
    fontSize: 13,
    fontWeight: '800',
    letterSpacing: 1.8,
    textTransform: 'uppercase',
  },
  homeTitle: {
    color: ink,
    fontFamily: Platform.select({ ios: 'Georgia', android: 'serif' }),
    fontSize: 48,
    fontWeight: '700',
    letterSpacing: -1.6,
    lineHeight: 52,
  },
  homeSubtitle: {
    maxWidth: 360,
    color: 'hsl(48, 24%, 25%)',
    fontFamily: Platform.select({ ios: 'Avenir Next', android: 'sans-serif' }),
    fontSize: 17,
    lineHeight: 25,
  },
  secondaryButton: {
    alignSelf: 'flex-start',
    marginTop: 16,
    borderWidth: 1,
    borderColor: moss,
    borderRadius: 999,
    paddingHorizontal: 22,
    paddingVertical: 14,
  },
  secondaryButtonText: {
    color: moss,
    fontFamily: Platform.select({ ios: 'Avenir Next', android: 'sans-serif-medium' }),
    fontSize: 15,
    fontWeight: '800',
  },
});
