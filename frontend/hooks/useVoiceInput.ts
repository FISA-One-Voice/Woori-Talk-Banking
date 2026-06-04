import type { VoiceState } from '@/components/VoiceStatusOverlay';
import { sendVoice } from '@/services/voiceService';
import type { VoiceResponseData } from '@/types/voice';
import { stopAllTts } from '@/utils/ttsManager';
import { Audio } from 'expo-av';
import { useCallback, useRef, useState } from 'react';

// Azure Speech는 WAV(PCM)만 지원 — 'lpcm' 문자열로 enum 없이 WAV 녹음
const RECORDING_OPTIONS: Audio.RecordingOptions = {
  android: {
    extension: '.wav',
    outputFormat: 6,  // RAW_AMR → pydub 변환 없이 Azure에 직접 전송 가능한 가장 근접한 포맷
    audioEncoder: 0,  // DEFAULT
    sampleRate: 16000,
    numberOfChannels: 1,
    bitRate: 256000,
  },
  ios: {
    extension: '.wav',
    outputFormat: 'lpcm' as any,  // IOSOutputFormat.LINEARPCM 의 실제 string 값
    audioQuality: 96,
    sampleRate: 16000,
    numberOfChannels: 1,
    bitRate: 256000,
    linearPCMBitDepth: 16,
    linearPCMIsBigEndian: false,
    linearPCMIsFloat: false,
  },
  web: {
    mimeType: 'audio/wav',
    bitsPerSecond: 256000,
  },
};

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
      await stopAllTts(); // 녹음 시작 전 화면 TTS 즉시 중단
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
      await recording.prepareToRecordAsync(RECORDING_OPTIONS);
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
