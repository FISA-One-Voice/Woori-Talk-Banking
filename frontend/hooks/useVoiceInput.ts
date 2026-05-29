import { Audio } from 'expo-av';
import { useCallback, useRef, useState } from 'react';
import type { VoiceState } from '@/components/VoiceStatusOverlay';
import { sendVoice } from '@/services/voiceService';
import type { VoiceResponseData } from '@/types/voice';

export type UseVoiceInputResult = {
  isRecording: boolean;
  handleLongPress: () => void;
  handlePressOut: () => void;
};

/**
 * 롱프레스 → 녹음 → 업로드 오케스트레이션 훅.
 *
 * @param onResponse - 음성 처리 성공 시 호출. _layout이 오디오 재생·네비게이션을 처리.
 * @param onError    - 실패 시 호출. code를 errorHandler.getTtsMessage()로 변환해 TTS 재생.
 * @param setVoiceState - 오버레이 상태 제어.
 */
export function useVoiceInput(
  onResponse: (data: VoiceResponseData) => void,
  onError: (code: string) => void,
  setVoiceState: (state: VoiceState) => void,
): UseVoiceInputResult {
  const recordingRef = useRef<Audio.Recording | null>(null);
  const [isRecording, setIsRecording] = useState(false);

  const handleLongPress = useCallback(async () => {
    try {
      const { granted } = await Audio.requestPermissionsAsync();
      if (!granted) {
        onError('MICROPHONE_PERMISSION_DENIED');
        return;
      }

      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      const recording = new Audio.Recording();
      await recording.prepareToRecordAsync({
        android: {
          extension: '.wav',
          outputFormat: 6,   // ENCODING_PCM_16BIT → WAV
          audioEncoder: 4,   // DEFAULT
          sampleRate: 16000,
          numberOfChannels: 1,
          bitRate: 256000,
        },
        ios: Audio.RecordingOptionsPresets.HIGH_QUALITY.ios,
        web: {},
      });
      await recording.startAsync();

      recordingRef.current = recording;
      setIsRecording(true);
      setVoiceState('recording');
    } catch {
      onError('VOICE_PROCESSING_ERROR');
    }
  }, [onError, setVoiceState]);

  const handlePressOut = useCallback(async () => {
    const recording = recordingRef.current;
    if (!recording) return;

    try {
      setIsRecording(false);
      setVoiceState('processing');

      await recording.stopAndUnloadAsync();
      recordingRef.current = null;

      // 녹음 모드 해제 후 재생 모드로 전환
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: false,
        playsInSilentModeIOS: true,
      });

      const uri = recording.getURI();
      if (!uri) {
        onError('VOICE_PROCESSING_ERROR');
        return;
      }

      if (__DEV__) {
        const status = await recording.getStatusAsync();
        console.log('[REC] uri:', uri);
        console.log('[REC] status:', JSON.stringify(status));
      }

      const data = await sendVoice(uri);
      onResponse(data);
    } catch (err) {
      recordingRef.current = null;
      const code = err instanceof Error ? err.message : 'VOICE_PROCESSING_ERROR';
      onError(code);
    }
  }, [onError, onResponse, setVoiceState]);

  return { isRecording, handleLongPress, handlePressOut };
}
