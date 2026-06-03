import { registerSound } from '@/utils/ttsManager';
import { Audio } from 'expo-av';
import React from 'react';

/**
 * base64 MP3를 재생하고 재생 완료 시 resolve 합니다.
 *
 * @param base64   - base64 인코딩된 MP3 데이터
 * @param soundRef - 제공 시 Sound 인스턴스를 ref에 저장 (화면 이탈 시 중단용).
 *                   미제공 시 전역 ttsManager에 등록되어 stopAllTts()로 중단 가능.
 */
export async function playBase64Audio(
  base64: string,
  soundRef?: React.MutableRefObject<Audio.Sound | null>,
): Promise<void> {
  const { sound } = await Audio.Sound.createAsync({
    uri: `data:audio/mpeg;base64,${base64}`,
  });

  if (soundRef) {
    soundRef.current = sound;
  } else {
    registerSound(sound);
  }

  return new Promise<void>((resolve) => {
    sound.setOnPlaybackStatusUpdate((status) => {
      if (status.isLoaded && status.didJustFinish) {
        sound.unloadAsync();
        if (!soundRef) registerSound(null);
        resolve();
      }
    });
    sound.playAsync().catch(() => {
      if (!soundRef) registerSound(null);
      resolve();
    });
  });
}
