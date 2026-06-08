import VoiceStatusOverlay, { VoiceState } from '@/components/VoiceStatusOverlay';
import { needsYesNoVoicePrompt, YES_NO_CONFIRM_INSTRUCTION } from '@/constants/voicePrompts';
import { useVoiceInput } from '@/hooks/useVoiceInput';
import { useAuthStore } from '@/store/authStore';
import { useTransferStore as transferStore } from '@/store/transferStore';
import { useVoiceResponseStore } from '@/store/voiceResponseStore';
import type { VoiceResponseData } from '@/types/voice';
import { playBase64Audio } from '@/utils/audioPlayer';
import { FALLBACK_MESSAGE } from '@/utils/errorHandler';
import { resetVoiceSessionOnHome } from '@/utils/resetVoiceSession';
import { speakText, stopAllTts } from '@/utils/ttsManager';
import { agentPathFromNavigateTo, shouldNavigateToRoute } from '@/utils/voiceNavigation';
import { Href, Stack, useRouter, useSegments } from 'expo-router';
import { useCallback, useEffect, useRef, useState, type MutableRefObject } from 'react';
import { GestureResponderEvent, Pressable, StyleSheet } from 'react-native';
import { useAutoTransferFlowStore } from './auto-transfer/store';

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
  const txId = (merged.txId as string) ?? (merged.tx_id as string) ?? '';
  if (!txId || !recipientName || !amount) return;
  transferStore.getState().setTxReceipt({
    txId,
    toName: recipientName,
    toBankName: (merged.toBankName as string) ?? '',
    amount,
  });
}

function buildAutoTransferReceiptFromSlots(prevSlots: Record<string, unknown>) {
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
  const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const longPressTouchStartRef = useRef<{ x: number; y: number } | null>(null);
  const isLongPressActiveRef = useRef(false);

  function handleTouchStart(e: GestureResponderEvent): void {
    const x = e.nativeEvent.locationX;
    const y = e.nativeEvent.locationY;
    touchPts.current = [{ x, y }];

    longPressTouchStartRef.current = { x, y };
    isLongPressActiveRef.current = false;
    longPressTimerRef.current = setTimeout(() => {
      longPressTimerRef.current = null;
      isLongPressActiveRef.current = true;
      handleLongPress();
    }, 500);
  }

  function handleTouchMove(e: GestureResponderEvent): void {
    const x = e.nativeEvent.locationX;
    const y = e.nativeEvent.locationY;
    touchPts.current.push({ x, y });

    if (longPressTimerRef.current && longPressTouchStartRef.current) {
      const dx = Math.abs(x - longPressTouchStartRef.current.x);
      const dy = Math.abs(y - longPressTouchStartRef.current.y);
      if (dx > 15 || dy > 15) {
        clearTimeout(longPressTimerRef.current);
        longPressTimerRef.current = null;
      }
    }
  }

  function handleTouchEnd(): void {
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }

    if (isLongPressActiveRef.current) {
      isLongPressActiveRef.current = false;
      handlePressOut();
    }

    const pts = touchPts.current;
    touchPts.current = [];
    if (isVGesture(pts)) {
      stopAllTts();
    }
  }

  // ── 음성 응답 처리 ──────────────────────────────────────────────────────────
  // 1) 음성 상태 즉시 업데이트
  // 2) expo-speech 폴백 중단 후 Azure TTS 재생 (await)
  // 3) 재생 완료 후 화면 전환 → useScreenAnnounce 와 겹치지 않는다

  const handleResponse = useCallback(
    async (data: VoiceResponseData) => {
      const prevSlots =
        (useVoiceResponseStore.getState().lastResponse?.collected_slots as
          | Record<string, unknown>
          | undefined) ?? {};

      const isCompleteNav = data.navigate_to === 'transfer/complete';
      const isFailedNav = data.navigate_to === 'transfer/failed';
      const isAutoCompleteNav = data.navigate_to === 'auto-transfer/complete';

      if (isFailedNav) {
        const mergedSlots = { ...prevSlots, ...(data.collected_slots ?? {}) };
        const errorMessage =
          (mergedSlots.transfer_error_message as string) ?? '';
        transferStore.getState().setTxReceipt(null);
        transferStore.getState().setTransferFailure({
          message: errorMessage || FALLBACK_MESSAGE,
        });
        navigateFromAgent(router, 'transfer/failed', currentPathRef);
        useVoiceResponseStore.getState().setLastResponse({
          ...data,
          collected_slots: mergedSlots,
        });
        if (data.audio) {
          await stopAllTts();
          await playBase64Audio(data.audio).catch(() => undefined);
        }
        navigateFromAgent(router, 'home', currentPathRef);
      } else if (isCompleteNav) {
        buildTxReceiptFromSlots(prevSlots, data.collected_slots);
        transferStore.getState().setTransferFailure(null);
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

      if (data.audio && !isFailedNav) {
        await stopAllTts();
        playBase64Audio(data.audio).catch(() => undefined);
      }

      if (needsYesNoVoicePrompt(data) && !data.audio) {
        speakText(YES_NO_CONFIRM_INSTRUCTION);
      }

      if (data.navigate_to && !isCompleteNav && !isAutoCompleteNav && !isFailedNav) {
        navigateFromAgent(router, data.navigate_to, currentPathRef);
      }
    },
    [router],
  );

  const handleError = useCallback((message: string) => {
    setVoiceState('idle');
    speakText(message);
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
