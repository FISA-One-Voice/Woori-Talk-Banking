import VoiceStatusOverlay, { VoiceState } from '@/components/VoiceStatusOverlay';
import { useVoiceInput } from '@/hooks/useVoiceInput';
import { useVoiceResponseStore } from '@/store/voiceResponseStore';
import { useTransferStore as transferStore } from '@/store/transferStore';
import { useAutoTransferFlowStore } from './auto-transfer/store';
import { useAuthStore } from '@/store/authStore';
import type { VoiceResponseData } from '@/types/voice';
import { apiClient, ApiResponse } from '@/utils/api';
import { resetVoiceSessionOnHome } from '@/utils/resetVoiceSession';
import { getTtsMessage } from '@/utils/errorHandler';
import {
  needsYesNoVoicePrompt,
  YES_NO_CONFIRM_INSTRUCTION,
} from '@/constants/voicePrompts';
import { registerSound, speakText, stopAllTts } from '@/utils/ttsManager';
import {
  agentPathFromNavigateTo,
  shouldNavigateToRoute,
} from '@/utils/voiceNavigation';
import { Audio } from 'expo-av';
import { Href, Stack, useRouter, useSegments } from 'expo-router';
import * as Speech from 'expo-speech';
import { useCallback, useEffect, useRef, useState, type MutableRefObject } from 'react';
import { GestureResponderEvent, Pressable, StyleSheet } from 'react-native';

// ── Azure TTS(base64) 재생 ────────────────────────────────────────────────────

async function playBase64Audio(base64: string): Promise<void> {
  const { sound } = await Audio.Sound.createAsync({
    uri: `data:audio/mpeg;base64,${base64}`,
  });
  registerSound(sound);

  return new Promise<void>((resolve) => {
    sound.setOnPlaybackStatusUpdate((status) => {
      if (status.isLoaded && status.didJustFinish) {
        sound.unloadAsync();
        registerSound(null);
        resolve();
      }
    });
    sound.playAsync().catch(() => {
      registerSound(null);
      resolve();
    });
  });
}

// ── V 제스처 감지 ─────────────────────────────────────────────────────────────

function isVGesture(pts: Array<{ x: number; y: number }>): boolean {
  if (pts.length < 8) return false;

  let bottomIdx = 0;
  for (let i = 1; i < pts.length; i++) {
    if (pts[i].y > pts[bottomIdx].y) bottomIdx = i;
  }

  const ratio = bottomIdx / (pts.length - 1);
  if (ratio < 0.2 || ratio > 0.8) return false;

  const startY = pts[0].y;
  const bottomY = pts[bottomIdx].y;
  const endY = pts[pts.length - 1].y;

  if (bottomY - startY < 80) return false;
  if (bottomY - endY < 60) return false;

  return true;
}

function segmentsToPath(segments: string[]): string {
  if (!segments.length) return '/';
  return `/${segments.join('/')}`;
}

function navigateFromAgent(
  router: ReturnType<typeof useRouter>,
  navigateTo: string,
  currentPathRef: MutableRefObject<string>,
): void {
  if (!shouldNavigateToRoute(currentPathRef.current, navigateTo)) {
    return;
  }

  const targetPath = agentPathFromNavigateTo(navigateTo);

  if (navigateTo === 'home') {
    resetVoiceSessionOnHome();
    router.replace('/home' as Href);
    currentPathRef.current = '/home';
    return;
  }

  router.replace(targetPath as Href);
  currentPathRef.current = targetPath;
}

function buildTxReceiptFromSlots(
  prevSlots: Record<string, unknown>,
  newSlots: Record<string, unknown> | undefined,
) {
  const merged = { ...prevSlots, ...(newSlots ?? {}) };
  const recipientName = (merged.recipient as string) ?? '';
  const amount = merged.amount ? Number(merged.amount) : 0;
  const txId =
    (merged.txId as string) ?? (merged.tx_id as string) ?? '';
  if (!recipientName || !amount) return;
  transferStore.getState().setTxReceipt({
    txId,
    toName: recipientName,
    toBankName: (merged.toBankName as string) ?? '',
    amount,
  });
}

function buildAutoTransferReceiptFromSlots(
  prevSlots: Record<string, unknown>,
) {
  const s = prevSlots;
  useAutoTransferFlowStore.getState().setReceipt({
    orderId: (s.orderId as string) ?? '',
    recipient: (s.recipient as string) ?? '',
    amount: s.amount ? Number(s.amount) : 0,
    cycle: (s.cycle as string) ?? '',
    scheduledDay: s.scheduled_day != null ? Number(s.scheduled_day) : null,
    scheduledDow: s.scheduled_dow != null ? Number(s.scheduled_dow) : null,
    bankName: (s.bank_name as string) ?? (s.bankName as string) ?? '',
  });
}

// ── 루트 레이아웃 ─────────────────────────────────────────────────────────────

export default function RootLayout() {
  const [voiceState, setVoiceState] = useState<VoiceState>('idle');
  const router = useRouter();
  const segments = useSegments();
  const currentPathRef = useRef('/');

  useEffect(() => {
    currentPathRef.current = segmentsToPath(segments as string[]);
  }, [segments]);

  const touchPts = useRef<Array<{ x: number; y: number }>>([]);

  function handleTouchStart(e: GestureResponderEvent): void {
    touchPts.current = [
      {
        x: e.nativeEvent.locationX,
        y: e.nativeEvent.locationY,
      },
    ];
  }

  function handleTouchMove(e: GestureResponderEvent): void {
    touchPts.current.push({
      x: e.nativeEvent.locationX,
      y: e.nativeEvent.locationY,
    });
  }

  function handleTouchEnd(): void {
    const pts = touchPts.current;
    touchPts.current = [];
    if (isVGesture(pts)) {
      stopAllTts();
    }
  }

  const handleResponse = useCallback(
    async (data: VoiceResponseData) => {
      const prevSlots =
        (useVoiceResponseStore.getState().lastResponse?.collected_slots as
          | Record<string, unknown>
          | undefined) ?? {};

      const isCompleteNav = data.navigate_to === 'transfer/complete';
      const isAutoCompleteNav = data.navigate_to === 'auto-transfer/complete';

      if (isCompleteNav) {
        buildTxReceiptFromSlots(prevSlots, data.collected_slots);
        navigateFromAgent(router, 'transfer/complete', currentPathRef);
        useVoiceResponseStore.getState().setLastResponse({
          ...data,
          collected_slots: { ...prevSlots, ...(data.collected_slots ?? {}) },
        });
      } else if (isAutoCompleteNav) {
        buildAutoTransferReceiptFromSlots(prevSlots);
        navigateFromAgent(router, 'auto-transfer/complete', currentPathRef);
        useVoiceResponseStore.getState().setLastResponse(data);
      } else {
        useVoiceResponseStore.getState().setLastResponse(data);
      }

      if (data.awaiting_asv_audio) {
        setVoiceState('awaiting_asv');
      } else if (data.awaiting_memo_decision) {
        setVoiceState('awaiting_memo');
      } else if (data.awaiting_confirmation || data.awaiting_transfer_clarification) {
        setVoiceState('awaiting_confirm');
      } else {
        setVoiceState('idle');
      }

      if (data.audio) {
        Speech.stop();
        await playBase64Audio(data.audio).catch(() => undefined);
      }

      if (needsYesNoVoicePrompt(data) && !data.audio) {
        speakText(YES_NO_CONFIRM_INSTRUCTION);
      }

      if (data.navigate_to && !isCompleteNav && !isAutoCompleteNav) {
        navigateFromAgent(router, data.navigate_to, currentPathRef);
      }
    },
    [router],
  );

  const handleError = useCallback((code: string) => {
    setVoiceState('idle');

    const errorMessage = getTtsMessage(code);

    apiClient
      .post<ApiResponse<{ audio_base64: string }>>('/api/voice/tts', {
        text: errorMessage,
        speed: 1.0,
      })
      .then(({ data }) => {
        if (data.success && data.data?.audio_base64) {
          playBase64Audio(data.data.audio_base64).catch(() => undefined);
        }
      })
      .catch(() => undefined);
  }, []);

  const { handleLongPress, handlePressOut } = useVoiceInput(
    handleResponse,
    handleError,
    setVoiceState,
  );

  const hasVoiceRegistered = useAuthStore((state) => state.hasVoiceRegistered);

  return (
    <Pressable
      style={styles.root}
      onLongPress={hasVoiceRegistered ? handleLongPress : undefined}
      onPressOut={hasVoiceRegistered ? handlePressOut : undefined}
      delayLongPress={500}
      onTouchStart={hasVoiceRegistered ? handleTouchStart : undefined}
      onTouchMove={hasVoiceRegistered ? handleTouchMove : undefined}
      onTouchEnd={hasVoiceRegistered ? handleTouchEnd : undefined}
    >
      <Stack screenOptions={{ headerShown: false }} />
      <VoiceStatusOverlay state={voiceState} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
});
