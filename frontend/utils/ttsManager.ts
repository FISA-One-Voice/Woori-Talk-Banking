import { Audio } from 'expo-av';
import * as Speech from 'expo-speech';
import { apiClient, ApiResponse } from '@/utils/api';

// ── expo-av Sound 추적 ────────────────────────────────────────────────────────

let _sound: Audio.Sound | null = null;

export function registerSound(sound: Audio.Sound | null): void {
  _sound = sound;
}

export async function stopAllTts(): Promise<void> {
  Speech.stop();
  if (_sound) {
    await _sound.stopAsync().catch(() => undefined);
    _sound = null;
  }
}

// ── Azure TTS 재생 ────────────────────────────────────────────────────────────

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

/**
 * 앱 전체 TTS 호출 함수 — Azure TTS API 사용.
 * expo-speech 대신 Azure TTS로 재생하여 음성 겹침을 방지한다.
 */
export function speakText(
  message: string,
  opts?: { onDone?: () => void; onStopped?: () => void },
): void {
  stopAllTts().then(() => {
    apiClient
      .post<ApiResponse<{ audio_base64: string }>>('/api/voice/tts', {
        text: message,
        speed: 1.0,
      })
      .then(({ data }) => {
        if (data.success && data.data?.audio_base64) {
          playBase64Audio(data.data.audio_base64)
            .then(() => opts?.onDone?.())
            .catch(() => opts?.onDone?.());
        } else {
          opts?.onDone?.();
        }
      })
      .catch(() => {
        // Azure 실패 시 expo-speech 폴백
        Speech.speak(message, {
          language: 'ko-KR',
          rate: 1.4,
          onDone: opts?.onDone,
          onStopped: opts?.onStopped,
        });
      });
  });
}

export const TTS_RATE = 1.4;
