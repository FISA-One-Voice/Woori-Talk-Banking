import { Audio } from 'expo-av';
import { Stack, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import { Pressable, StyleSheet } from 'react-native';
import VoiceStatusOverlay, { VoiceState } from '@/components/VoiceStatusOverlay';
import { useVoiceInput } from '@/hooks/useVoiceInput';
import type { VoiceResponseData } from '@/types/voice';
import { apiClient, ApiResponse } from '@/utils/api';
import { getTtsMessage } from '@/utils/errorHandler';

async function playBase64Audio(base64: string): Promise<void> {
  const { sound } = await Audio.Sound.createAsync({
    uri: `data:audio/mpeg;base64,${base64}`,
  });
  await sound.playAsync();
  // 재생 완료 후 메모리 해제
  sound.setOnPlaybackStatusUpdate((status) => {
    if (status.isLoaded && status.didJustFinish) {
      sound.unloadAsync();
    }
  });
}

export default function RootLayout() {
  const [voiceState, setVoiceState] = useState<VoiceState>('idle');
  const router = useRouter();

  const handleResponse = useCallback(
    (data: VoiceResponseData) => {
      if (data.audio) {
        playBase64Audio(data.audio).catch(() => undefined);
      }

      if (data.navigate_to) {
        router.push(`/${data.navigate_to}`);
      }

      if (data.awaiting_asv_audio) {
        setVoiceState('awaiting_asv');
      } else if (data.awaiting_confirmation) {
        setVoiceState('awaiting_confirm');
      } else {
        setVoiceState('idle');
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
    >
      <Stack screenOptions={{ headerShown: false }} />
      <VoiceStatusOverlay state={voiceState} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
});
