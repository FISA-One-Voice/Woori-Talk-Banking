import { create } from 'zustand';
import type { VoiceResponseData } from '@/types/voice';

interface VoiceResponseState {
  lastResponse: VoiceResponseData | null;
  setLastResponse: (data: VoiceResponseData) => void;
  clearLastResponse: () => void;
}

export const useVoiceResponseStore = create<VoiceResponseState>((set) => ({
  lastResponse: null,
  setLastResponse: (data) => set({ lastResponse: data }),
  clearLastResponse: () => set({ lastResponse: null }),
}));