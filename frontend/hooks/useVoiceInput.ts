import type { VoiceState } from '@/components/VoiceStatusOverlay';
import { sendVoice } from '@/services/voiceService';
import type { VoiceResponseData } from '@/types/voice';
import { extractApiErrorMessage, getClientErrorMessage } from '@/utils/errorHandler';
import { stopAllTts } from '@/utils/ttsManager';
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
  onError: (message: string) => void,
  setVoiceState: (state: VoiceState) => void,
): UseVoiceInputResult {
  const recordingRef = useRef<Audio.Recording | null>(null);
  const [isRecording, setIsRecording] = useState(false);

  const handleLongPress = useCallback(async () => {
    try {
      const { granted } = await Audio.requestPermissionsAsync();
      if (!granted) {
        onError(getClientErrorMessage('MICROPHONE_PERMISSION_DENIED'));
        return;
      }

      await stopAllTts();
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      const recording = new Audio.Recording();
      await recording.prepareToRecordAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
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
        onError(getClientErrorMessage('VOICE_PROCESSING_ERROR'));
        return;
      }

      const data = await sendVoice(uri);
      onResponse(data);
    } catch (err) {
      recordingRef.current = null;
      // [버그] 네트워크 오류 등으로 catch에 떨어지면 audio session이 recording 모드로 남아
      // 다음 녹음 시도 시 prepareToRecordAsync가 실패해 마이크 꾹 누르기가 안 됨.
      // 수정 방법: 아래 코드를 catch 블록에 추가
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: false,
        playsInSilentModeIOS: true,
      }).catch(() => undefined);
      onError(extractApiErrorMessage(err));
    }
  }, [onError, onResponse, setVoiceState]);

  return { isRecording, handleLongPress, handlePressOut };
}
