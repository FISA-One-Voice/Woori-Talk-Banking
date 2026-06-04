// =============================================================================
// frontend/store/authStore.ts
//
// [역할]
// 로그인 토큰을 앱 전체에서 공유하는 Zustand 스토어.
// 화면 간에 토큰을 직접 넘기지 않고, 이 스토어에서 꺼내 씁니다.
//
// [DEV 사용법]
// 1. 백엔드 서버 켜기
// 2. POST /jwt-auth/login 으로 accessToken 발급
// 3. 이벤트 상세 화면 하단 DEV 입력창에 붙여넣기
// 4. 이후 API 호출 시 자동으로 Bearer 헤더에 첨부됨
// =============================================================================

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import * as SecureStore from 'expo-secure-store';

// react-native-encrypted-storage와 동일한 역할을 하는 Expo 호환 안전 저장소입니다.
const secureStorage = {
  getItem: async (name: string) => {
    return (await SecureStore.getItemAsync(name)) || null;
  },
  setItem: async (name: string, value: string) => {
    await SecureStore.setItemAsync(name, value);
  },
  removeItem: async (name: string) => {
    await SecureStore.deleteItemAsync(name);
  },
};

interface AuthState {
  token: string | null;
  refreshToken: string | null;
  hasVoiceRegistered: boolean;
  ttsSpeed: number;
  setTokens: (accessToken: string, refreshToken: string, hasVoiceRegistered?: boolean, ttsSpeed?: number) => void;
  setHasVoiceRegistered: (status: boolean) => void;
  clearTokens: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      refreshToken: null,
      hasVoiceRegistered: false,
      ttsSpeed: 1.7,
      setTokens: (token, refreshToken, hasVoiceRegistered = false, ttsSpeed) =>
        set((state) => ({
          token,
          refreshToken,
          hasVoiceRegistered: hasVoiceRegistered ?? state.hasVoiceRegistered,
          ttsSpeed: ttsSpeed ?? state.ttsSpeed,
        })),
      setHasVoiceRegistered: (status) => set({ hasVoiceRegistered: status }),
      clearTokens: () => set({ token: null, refreshToken: null, hasVoiceRegistered: false, ttsSpeed: 1.7 }),
    }),
    {
      name: 'auth-storage',
      storage: createJSONStorage(() => secureStorage),
    }
  )
);
