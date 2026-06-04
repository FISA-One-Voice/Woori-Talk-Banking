import VoiceStatusOverlay, { VoiceState } from '@/components/VoiceStatusOverlay';
import { useVoiceInput } from '@/hooks/useVoiceInput';
import { useVoiceResponseStore } from '@/store/voiceResponseStore';
import { useTransferStore as transferStore } from '@/store/transferStore';
import type { VoiceResponseData } from '@/types/voice';
import { apiClient, ApiResponse } from '@/utils/api';
import { getTtsMessage } from '@/utils/errorHandler';
import { registerSound, stopAllTts } from '@/utils/ttsManager';
import { Audio } from 'expo-av';
import { Stack, useRouter } from 'expo-router';
import * as Speech from 'expo-speech';
import { useCallback, useRef, useState } from 'react';
import { GestureResponderEvent, Pressable, StyleSheet } from 'react-native';

// ── Azure TTS(base64) 재생 ────────────────────────────────────────────────────
// 재생이 완전히 끝날 때 resolve 한다 (navigate 전에 await 해서 TTS 겹침 방지).

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
// 터치 경로가 V 모양(↘ → ↗)을 그리면 true.

function isVGesture(pts: Array<{ x: number; y: number }>): boolean {
  if (pts.length < 8) return false;

  // 최저점(V의 꼭짓점) 인덱스 탐색
  let bottomIdx = 0;
  for (let i = 1; i < pts.length; i++) {
    if (pts[i].y > pts[bottomIdx].y) bottomIdx = i;
  }

  // 최저점이 전체 경로의 20%~80% 구간에 있어야 한다 (시작/끝이 아닌 중간)
  const ratio = bottomIdx / (pts.length - 1);
  if (ratio < 0.2 || ratio > 0.8) return false;

  const startY = pts[0].y;
  const bottomY = pts[bottomIdx].y;
  const endY = pts[pts.length - 1].y;

  // 아래로 80px 이상 내려가야 한다
  if (bottomY - startY < 80) return false;

  // 다시 위로 60px 이상 올라와야 한다
  if (bottomY - endY < 60) return false;

  return true;
}

// ── 루트 레이아웃 ─────────────────────────────────────────────────────────────

export default function RootLayout() {
  const [voiceState, setVoiceState] = useState<VoiceState>('idle');
  const router = useRouter();

  // V 제스처: 터치 경로를 수집한다
  const touchPts = useRef<Array<{ x: number; y: number }>>([]);
  // Long press 타이머 (카드 위에서도 동작하도록 onTouchStart 기반으로 구현)
  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const touchOrigin = useRef<{ x: number; y: number } | null>(null);

  function handleTouchStart(e: GestureResponderEvent): void {
    const { locationX: x, locationY: y } = e.nativeEvent;
    touchPts.current = [{ x, y }];
    touchOrigin.current = { x, y };

    // 500ms 유지하면 녹음 시작 — onLongPress 대신 사용해 자식 컴포넌트 위에서도 동작
    longPressTimer.current = setTimeout(() => {
      longPressTimer.current = null;
      handleLongPress();
    }, 500);
  }

  function handleTouchMove(e: GestureResponderEvent): void {
    const { locationX: x, locationY: y } = e.nativeEvent;
    touchPts.current.push({ x, y });

    // 15px 이상 움직이면 long press 취소 (V 제스처 or 스크롤)
    if (longPressTimer.current && touchOrigin.current) {
      const dx = Math.abs(x - touchOrigin.current.x);
      const dy = Math.abs(y - touchOrigin.current.y);
      if (dx > 15 || dy > 15) {
        clearTimeout(longPressTimer.current);
        longPressTimer.current = null;
      }
    }
  }

  function handleTouchEnd(): void {
    // Long press 타이머가 아직 살아있으면 취소 (short tap)
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current);
      longPressTimer.current = null;
    }
    touchOrigin.current = null;

    // V 제스처 감지
    const pts = touchPts.current;
    touchPts.current = [];
    if (isVGesture(pts)) {
      stopAllTts();
    }

    // 녹음 중이면 종료 (내부에서 recording 유무 확인하므로 항상 호출 가능)
    handlePressOut();
  }

  // ── 음성 응답 처리 ──────────────────────────────────────────────────────────
  // 1) 음성 상태 즉시 업데이트
  // 2) 기존 expo-speech 중단 후 Azure TTS 재생 (await)
  // 3) 재생 완료 후 화면 전환 → useScreenAnnounce 와 겹치지 않는다

  const handleResponse = useCallback(
    async (data: VoiceResponseData) => {
      // execute_node는 collected_slots를 {}로 초기화하므로
      // setLastResponse 이전에 이전 슬롯을 저장해 이체 완료 화면에 전달한다.
      const prevSlots = useVoiceResponseStore.getState().lastResponse?.collected_slots ?? {};

      useVoiceResponseStore.getState().setLastResponse(data);

      if (data.awaiting_asv_audio) {
        setVoiceState('awaiting_asv');
      } else if (data.awaiting_confirmation) {
        setVoiceState('awaiting_confirm');
      } else {
        setVoiceState('idle');
      }

      if (data.navigate_to === 'transfer/complete') {
        const recipientName = (prevSlots.recipient as string) ?? '';
        const amount = prevSlots.amount ? Number(prevSlots.amount) : 0;
        if (recipientName && amount) {
          transferStore.getState().setTxReceipt({
            txId: '',
            toName: recipientName,
            toBankName: '',
            amount,
          });
        }
      }

      // 화면 이동과 TTS를 동시에 — 화면이 열리는 동안 에이전트 음성이 재생됨
      if (data.navigate_to) {
        if (data.navigate_to === 'home') {
          router.replace('/home');
        } else {
          router.push(`/${data.navigate_to}`);
        }
      }

      if (data.audio) {
        Speech.stop();
        playBase64Audio(data.audio).catch(() => undefined); // await 제거 — 화면 이동과 동시 재생
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

  return (
    <Pressable
      style={styles.root}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
    >
      <Stack screenOptions={{ headerShown: false }} />
      <VoiceStatusOverlay state={voiceState} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
});
