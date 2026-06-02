// =============================================================================
// frontend/store/authStore.ts
// =============================================================================

import { create } from 'zustand';

interface AuthState {
  /** JWT accessToken. 없으면 null. */
  token: string | null;
  /** JWT refreshToken. 없으면 null. */
  refreshToken: string | null;
  /** 로그인 시 입력한 전화번호 (Face ID 재로그인용) */
  phone: string | null;

  /** 토큰 쌍 및 전화번호 저장 (로그인 성공 시 호출) */
  setTokens: (accessToken: string, refreshToken: string, phone?: string) => void;

  /** 모든 토큰 삭제 (로그아웃 시 호출) */
  clearTokens: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  refreshToken: null,
  phone: null,

  setTokens: (token, refreshToken, phone) =>
    set((state) => ({
      token,
      refreshToken,
      phone: phone !== undefined ? phone : state.phone,
    })),

  clearTokens: () => set({ token: null, refreshToken: null, phone: null }),
}));
