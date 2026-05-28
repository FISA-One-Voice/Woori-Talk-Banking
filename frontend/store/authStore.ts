// =============================================================================
// frontend/store/authStore.ts
//
// [역할]
// 로그인 토큰을 앱 전체에서 공유하는 Zustand 스토어.
// API 호출 시 axios 인터셉터(api.ts)가 여기서 토큰을 꺼내 자동으로 헤더에 첨부합니다.
// =============================================================================

import { create } from 'zustand';

interface AuthState {
  /** JWT accessToken. 없으면 null. */
  token: string | null;
  /** JWT refreshToken. 없으면 null. */
  refreshToken: string | null;

  /** 토큰 쌍 저장 (로그인 성공 및 토큰 갱신 시 호출) */
  setTokens: (accessToken: string, refreshToken: string) => void;

  /** 모든 토큰 삭제 (로그아웃 시 호출) */
  clearTokens: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  refreshToken: null,

  setTokens: (token, refreshToken) => set({ token, refreshToken }),

  clearTokens: () => set({ token: null, refreshToken: null }),
}));
