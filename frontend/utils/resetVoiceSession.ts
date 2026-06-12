import { useTransferStore } from '@/store/transferStore';
import { useVoiceResponseStore } from '@/store/voiceResponseStore';
import { apiClient } from '@/utils/api';

/** 홈 복귀 시 LangGraph·Zustand 음성 세션 초기화 */
export function resetVoiceSessionOnHome(): void {
  useTransferStore.getState().reset();
  useVoiceResponseStore.getState().clearLastResponse();
  apiClient.post('/api/voice/reset-state').catch(() => undefined);
}
