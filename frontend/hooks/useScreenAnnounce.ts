// =============================================================================
// frontend/hooks/useScreenAnnounce.ts
//
// [이 훅의 역할]
// 화면이 포커스를 얻을 때마다(첫 진입 / 뒤로가기 / 딥링크 등 모든 경로)
// message 를 TTS 로 읽어줍니다.
//
// [사용 예]
//   useScreenAnnounce('이벤트 목록 화면입니다.');
//
// [동작]
// - 화면 진입 → Speech.speak(message)
// - 화면 이탈 → Speech.stop()  (다음 화면 TTS 와 겹치지 않도록)
// =============================================================================

import { useFocusEffect } from 'expo-router';
import * as Speech from 'expo-speech';
import { useCallback } from 'react';

export function useScreenAnnounce(message: string): void {
  useFocusEffect(
    useCallback(() => {
      if (!message) return;
      Speech.speak(message, { language: 'ko-KR' });
      return () => {
        Speech.stop();
      };
    }, [message]),
  );
}
