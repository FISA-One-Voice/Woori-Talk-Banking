// =============================================================================
// frontend/hooks/useScreenAnnounce.ts
//
// [이 훅의 역할]
// 화면이 포커스를 얻을 때마다(첫 진입 / 뒤로가기 / 딥링크 등 모든 경로)
// message 를 Azure TTS(백엔드)로 읽어줍니다.
//
// [사용 예]
//   useScreenAnnounce('이벤트 목록 화면입니다.');
//
// [동작]
// - 화면 진입 → POST /api/voice/tts → Azure 음성 재생
// - 화면 이탈 → 재생 중인 오디오 중단 (다음 화면 TTS 와 겹치지 않도록)
// =============================================================================

import { playBase64Audio } from '@/utils/audioPlayer';
import { fetchTtsAudio } from '@/services/voiceService';
import { Audio } from 'expo-av';
import { useFocusEffect } from 'expo-router';
import { useCallback, useRef } from 'react';

export function useScreenAnnounce(message: string): void {
  const soundRef = useRef<Audio.Sound | null>(null);

  useFocusEffect(
    useCallback(() => {
      if (!message) return;
      fetchTtsAudio(message)
        .then(base64 => playBase64Audio(base64, soundRef))
        .catch(() => undefined);
      return () => {
        soundRef.current?.stopAsync().catch(() => undefined);
        soundRef.current?.unloadAsync().catch(() => undefined);
        soundRef.current = null;
      };
    }, [message]),
  );
}
