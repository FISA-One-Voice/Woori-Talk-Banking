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

  /** 토큰 저장 (로그인 성공 시 호출) */
  setToken: (token: string) => void;

  /** 토큰 삭제 (로그아웃 시 호출) */
  clearToken: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,

  setToken: (token) => set({ token }),

  clearToken: () => set({ token: null }),
}));
