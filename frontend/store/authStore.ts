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
