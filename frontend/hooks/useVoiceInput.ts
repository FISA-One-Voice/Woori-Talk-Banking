import type { VoiceState } from '@/components/VoiceStatusOverlay';
import { sendVoice } from '@/services/voiceService';
import type { VoiceResponseData } from '@/types/voice';
import { Audio } from 'expo-av';
import { useCallback, useRef, useState } from 'react';

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
  const isPressingRef = useRef<boolean>(false);
  const [isRecording, setIsRecording] = useState(false);

  const handleLongPress = useCallback(async () => {
    isPressingRef.current = true;
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
      await recording.prepareToRecordAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);

      // 🔥 녹음 준비(약 0.5초)가 끝났는데 사용자가 이미 손을 뗐다면 시작하지 않고 즉시 취소!
      if (!isPressingRef.current) {
        return;
      }

      await recording.startAsync();

      // 🔥 startAsync 직후에도 확인해서 혹시 그 찰나에 손을 뗐다면 즉시 종료
      if (!isPressingRef.current) {
        await recording.stopAndUnloadAsync();
        return;
      }

      recordingRef.current = recording;
      setIsRecording(true);
      setVoiceState('recording');
    } catch {
      onError('VOICE_PROCESSING_ERROR');
    }
  }, [onError, setVoiceState]);

  const handlePressOut = useCallback(async () => {
    isPressingRef.current = false; // 손을 떼었음을 기록

    const recording = recordingRef.current;
    
    // 🔥 아직 녹음 객체가 생성되기도 전에 손을 뗀 경우 무시
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
