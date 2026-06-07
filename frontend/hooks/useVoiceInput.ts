import type { VoiceState } from '@/components/VoiceStatusOverlay';
import { sendVoice } from '@/services/voiceService';
import type { VoiceResponseData } from '@/types/voice';
import { stopAllTts } from '@/utils/ttsManager';
import { extractApiErrorMessage, getClientErrorMessage } from '@/utils/errorHandler';
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
 */
export function useVoiceInput(
  onResponse: (data: VoiceResponseData) => void,
  onError: (message: string) => void,
  setVoiceState: (state: VoiceState) => void,
): UseVoiceInputResult {
  const recordingRef = useRef<Audio.Recording | null>(null);
  const isPressingRef = useRef(false); // 🔥 사용자가 손을 떼었는지 추적하는 변수
  const isStartingRef = useRef(false); // 🔥 녹음 준비 중 중복 호출 방지 (동기 플래그)
  const [isRecording, setIsRecording] = useState(false);

  const handleLongPress = useCallback(async () => {
    if (recordingRef.current || isStartingRef.current) return; // 이미 녹음 중이거나 준비 중이면 무시
    isStartingRef.current = true;
    isPressingRef.current = true;
    try {
      await stopAllTts(); // 녹음 시작 전 화면 TTS 즉시 중단
      const { granted } = await Audio.requestPermissionsAsync();
      if (!granted) {
        onError(getClientErrorMessage('MICROPHONE_PERMISSION_DENIED'));
        return;
      }

      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      const recording = new Audio.Recording();
      await recording.prepareToRecordAsync(RECORDING_OPTIONS);
      
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
      isStartingRef.current = false;
      setIsRecording(true);
      setVoiceState('recording');
    } catch {
      isStartingRef.current = false;
      onError('VOICE_PROCESSING_ERROR');
    }
  }, [onError, setVoiceState]);

  const handlePressOut = useCallback(async () => {
    isPressingRef.current = false; // 손을 떼었음을 기록
    
    const recording = recordingRef.current;

    // 🔥 아직 녹음 객체가 생성되기도 전에 손을 뗀 경우,
    // handleLongPress 안의 if (!isPressingRef.current)에서 알아서 취소하므로 무시하고 넘김.
    if (!recording) return;
    recordingRef.current = null; // 🔥 즉시 null로 설정 — onPressOut + handleTouchEnd 중복 호출 방지

    try {
      setIsRecording(false);
      setVoiceState('processing');

      await recording.stopAndUnloadAsync();

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
      onError(extractApiErrorMessage(err));
    }
  }, [onError, onResponse, setVoiceState]);

  return { isRecording, handleLongPress, handlePressOut };
} 
