import { Audio } from 'expo-av';
import { apiClient } from '@/utils/api';

// 현재 재생 중인 사운드 (전역 싱글턴)
let _currentSound: Audio.Sound | null = null;

/** 현재 재생 중인 TTS를 즉시 멈춘다 */
export async function stopCurrentTts(): Promise<void> {
  if (_currentSound) {
    try {
      await _currentSound.stopAsync();
      await _currentSound.unloadAsync();
    } catch {
      // 이미 언로드됐으면 무시
    }
    _currentSound = null;
  }
}

/** 텍스트를 TTS로 재생한다. 이전 재생 중인 오디오는 자동으로 멈춘다 */
export async function playTts(text: string): Promise<void> {
  await stopCurrentTts();

  try {
    const res = await apiClient.post('/api/voice/tts', { text, speed: 1.0 });
    if (!res.data.success) return;

    const base64 = res.data.data.audio_base64;
    await Audio.setAudioModeAsync({ playsInSilentModeIOS: true });

    const { sound } = await Audio.Sound.createAsync(
      { uri: `data:audio/mpeg;base64,${base64}` },
      { shouldPlay: true }
    );
    _currentSound = sound;

    sound.setOnPlaybackStatusUpdate((status) => {
      if (status.isLoaded && status.didJustFinish) {
        sound.unloadAsync();
        if (_currentSound === sound) _currentSound = null;
      }
    });
  } catch {
    // TTS 실패는 무시
  }
}
