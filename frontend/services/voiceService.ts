import { VoiceResponseData } from '@/types/voice';
import { ApiResponse, apiClient } from '@/utils/api';

/**
 * 녹음 파일을 백엔드 음성 파이프라인으로 전송하고 응답 데이터를 반환합니다.
 *
 * @param audioUri - expo-av가 반환한 로컬 녹음 파일 URI (file://...)
 * @returns VoiceResponseData — 오디오(base64), navigate_to, 슬롯, 상태 플래그
 * @throws Error — message에 백엔드 에러 코드가 담김. errorHandler.getTtsMessage()로 변환 가능.
 */
export async function sendVoice(audioUri: string): Promise<VoiceResponseData> {
  const formData = new FormData();

  // React Native의 FormData는 런타임에 {uri, type, name} 객체를 File처럼 처리하지만
  // TypeScript 타입 서명은 Blob을 요구하므로 unknown을 경유해 캐스팅합니다.
  formData.append('audio', {
    uri: audioUri,
    type: 'audio/m4a',
    name: 'recording.m4a',
  } as unknown as Blob);

  const { data } = await apiClient.post<ApiResponse<VoiceResponseData>>(
    '/api/voice/voice',
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 30000,
    },
  );

  if (!data.success || !data.data) {
    throw new Error(data.code ?? 'VOICE_PROCESSING_ERROR');
  }

  if (__DEV__) {
    console.log('[STT]', data.data.transcript ?? '(인식 결과 없음)');
    console.log('[Agent] navigate_to=%s pending=%s', data.data.navigate_to, data.data.pending_action);
    console.log('[Agent] slots=%o', data.data.collected_slots);
    console.log('[Agent] awaiting_confirmation=%s awaiting_asv=%s', data.data.awaiting_confirmation, data.data.awaiting_asv_audio);
  }

  return data.data;
}
