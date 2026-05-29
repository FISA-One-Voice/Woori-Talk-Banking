import { Audio } from 'expo-av';
import { Stack, useRouter } from 'expo-router';
import * as Speech from 'expo-speech';
import { useCallback, useRef } from 'react';
import { GestureResponderEvent, Pressable, StyleSheet } from 'react-native';
import VoiceStatusOverlay, { VoiceState } from '@/components/VoiceStatusOverlay';
import { useVoiceInput } from '@/hooks/useVoiceInput';
import { useVoiceResponseStore } from '@/store/voiceResponseStore';
import type { VoiceResponseData } from '@/types/voice';
import { apiClient, ApiResponse } from '@/utils/api';
import { getTtsMessage } from '@/utils/errorHandler';
import { registerSound, stopAllTts } from '@/utils/ttsManager';
import { useState } from 'react';

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

  const startY  = pts[0].y;
  const bottomY = pts[bottomIdx].y;
  const endY    = pts[pts.length - 1].y;

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

  function handleTouchStart(e: GestureResponderEvent): void {
    touchPts.current = [{
      x: e.nativeEvent.locationX,
      y: e.nativeEvent.locationY,
    }];
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

  // ── 음성 응답 처리 ──────────────────────────────────────────────────────────
  // 1) 음성 상태 즉시 업데이트
  // 2) 기존 expo-speech 중단 후 Azure TTS 재생 (await)
  // 3) 재생 완료 후 화면 전환 → useScreenAnnounce 와 겹치지 않는다

  const handleResponse = useCallback(
    async (data: VoiceResponseData) => {
      useVoiceResponseStore.getState().setLastResponse(data);

      if (data.awaiting_asv_audio) {
        setVoiceState('awaiting_asv');
      } else if (data.awaiting_confirmation) {
        setVoiceState('awaiting_confirm');
      } else {
        setVoiceState('idle');
      }

      if (data.audio) {
        Speech.stop(); // 화면 안내 TTS가 재생 중이면 먼저 중단
        await playBase64Audio(data.audio).catch(() => undefined);
      }

      if (data.navigate_to) {
        if (data.navigate_to === 'home') {
          router.replace('/home');
        } else {
          router.push(`/${data.navigate_to}`);
        }
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
      onLongPress={handleLongPress}
      onPressOut={handlePressOut}
      delayLongPress={500}
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
