// =============================================================================
// frontend/context/MicContext.tsx
// 홀드 방식: 누르는 순간 녹음 시작, 손 떼는 순간 전송
// =============================================================================

import { Audio } from 'expo-av';
import { router } from 'expo-router';
import {
  createContext,
  ReactNode,
  useContext,
  useRef,
  useState,
} from 'react';
import { apiClient } from '@/utils/api';
import { stopAllTts } from '@/utils/ttsManager';
import * as FileSystem from 'expo-file-system';

export type VoiceState = 'idle' | 'listening' | 'processing' | 'error';

interface VoiceResponseData {
  audio: string;
  navigate_to: string | null;
  collected_slots: Record<string, unknown>;
  awaiting_confirmation: boolean;
  awaiting_asv_audio: boolean;
  transcript: string | null;
}

interface MicContextType {
  voiceState: VoiceState;
  activateMic: () => void;  // onPressIn: 녹음 시작
  stopMic: () => void;       // onPressOut: 전송
}

const MicContext = createContext<MicContextType>({
  voiceState: 'idle',
  activateMic: () => {},
  stopMic: () => {},
});

const NAVIGATE_MAP: Record<string, string> = {
  asset: '/asset',
  'asset/history': '/asset/history',
  transfer: '/transfer',
  'auto-transfer': '/auto-transfer',
  event: '/dev/event',
};

export function MicProvider({ children }: { children: ReactNode }) {
  const [voiceState, setVoiceState] = useState<VoiceState>('idle');
  const recordingRef = useRef<Audio.Recording | null>(null);
  const soundRef = useRef<Audio.Sound | null>(null);
  const stopRequestedRef = useRef(false);
  const isPreparingRef = useRef(false); // 중복 준비 방지

  async function activateMic(): Promise<void> {
    if (isPreparingRef.current) return;
    if (voiceState !== 'idle' && voiceState !== 'error') return;

    isPreparingRef.current = true;
    stopRequestedRef.current = false;

    // TTS 재생 중이면 즉시 멈추기
    await stopAllTts();
    setVoiceState('listening');

    try {
      const { granted } = await Audio.requestPermissionsAsync();
      if (!granted) {
        setVoiceState('error');
        setTimeout(() => setVoiceState('idle'), 2000);
        return;
      }

      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      const recording = new Audio.Recording();
      // 16kHz 모노 AAC - Clova STT 권장 포맷
      await recording.prepareToRecordAsync({
        isMeteringEnabled: false,
        android: {
          extension: '.m4a',
          outputFormat: 2,   // MPEG_4
          audioEncoder: 3,   // AAC
          sampleRate: 16000,
          numberOfChannels: 1,
          bitRate: 64000,
        },
        ios: {
          extension: '.m4a',
          outputFormat: 'aac ' as any,
          audioQuality: 96,
          sampleRate: 16000,
          numberOfChannels: 1,
          bitRate: 64000,
          linearPCMBitDepth: 16,
          linearPCMIsBigEndian: false,
          linearPCMIsFloat: false,
        },
        web: {},
      });
      await recording.startAsync();
      recordingRef.current = recording;

      if (stopRequestedRef.current) {
        await _stopAndSend();
      }
    } catch (e) {
      console.error('녹음 시작 실패:', e);
      setVoiceState('error');
      setTimeout(() => setVoiceState('idle'), 2000);
    } finally {
      isPreparingRef.current = false;
    }
  }

  async function stopMic(): Promise<void> {
    if (voiceState === 'processing') return;

    if (!recordingRef.current) {
      // 아직 녹음 준비 중 — 준비 완료 후 자동 전송하도록 플래그 세팅
      stopRequestedRef.current = true;
      return;
    }

    await _stopAndSend();
  }

  async function _stopAndSend(): Promise<void> {
    if (!recordingRef.current) return;
    setVoiceState('processing');

    try {
      await recordingRef.current.stopAndUnloadAsync();
      const uri = recordingRef.current.getURI();
      recordingRef.current = null;

      if (!uri) throw new Error('녹음 파일 없음');

      // 파일 포맷 확인 (첫 8바이트 hex)
      const base64Header = await FileSystem.readAsStringAsync(uri, {
        encoding: 'base64' as any,
        length: 8,
        position: 0,
      });
      const headerBytes = atob(base64Header).split('').map(c => c.charCodeAt(0).toString(16).padStart(2, '0')).join('');
      console.log('[MIC] 파일 헤더 hex:', headerBytes, '| URI:', uri.slice(-20));

      const formData = new FormData();
      formData.append('audio', {
        uri,
        name: 'audio.mp4',
        type: 'audio/mp4',
      } as unknown as Blob);

      const res = await apiClient.post<{ success: boolean; data: VoiceResponseData }>(
        '/api/voice/voice',
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );

      const data = res.data.data;

      if (data.audio) {
        await _playBase64Audio(data.audio);
      }

      if (data.navigate_to) {
        let destination = NAVIGATE_MAP[data.navigate_to] ?? `/${data.navigate_to}`;
        const action = (data.collected_slots as Record<string, string>)?.action;
        if (data.navigate_to === 'asset' && (action === 'history' || action === 'category')) {
          destination = '/asset/history';
        }
        router.push(destination as never);
      }

      setVoiceState('idle');
    } catch (e: any) {
      const body = e?.response?.data;
      console.error('음성 전송 실패 상세:', JSON.stringify(body));
      setVoiceState('error');
      setTimeout(() => setVoiceState('idle'), 2000);
    } finally {
      await Audio.setAudioModeAsync({ allowsRecordingIOS: false });
    }
  }

  async function _playBase64Audio(base64: string): Promise<void> {
    try {
      if (soundRef.current) {
        await soundRef.current.unloadAsync();
        soundRef.current = null;
      }
      const { sound } = await Audio.Sound.createAsync(
        { uri: `data:audio/mpeg;base64,${base64}` },
        { shouldPlay: true }
      );
      soundRef.current = sound;
    } catch {
      // TTS 재생 실패는 무시
    }
  }

  return (
    <MicContext.Provider value={{ voiceState, activateMic, stopMic }}>
      {children}
    </MicContext.Provider>
  );
}

export function useMic(): MicContextType {
  return useContext(MicContext);
}
