// =============================================================================
// frontend/utils/api.ts
//
// [이 파일의 역할]
// 백엔드 API 호출을 위한 axios 인스턴스를 설정합니다.
// 모든 API 요청은 이 파일의 apiClient를 통해 이루어집니다.
//
// [BASE_URL 설정 방법]
// frontend/.env 파일에 아래 항목을 추가하세요:
//   EXPO_PUBLIC_API_BASE_URL=http://본인_로컬IP:8000
// =============================================================================

import axios from 'axios';
import { useAuthStore } from '@/store/authStore';

if (__DEV__ && !process.env['EXPO_PUBLIC_API_BASE_URL']) {
  console.warn(
    '[api.ts] EXPO_PUBLIC_API_BASE_URL 환경변수가 설정되지 않았습니다.\n' +
    'frontend/.env.example 을 복사해 frontend/.env 를 만들고 본인 IP를 입력하세요.'
  );
}

const BASE_URL = process.env['EXPO_PUBLIC_API_BASE_URL'] ?? 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ✅ 토큰 인터셉터 추가 (Zustand authStore 연동)
// 매번 API 요청을 보낼 때마다 이 함수가 실행되어 자동으로 토큰을 헤더에 삽입합니다.
apiClient.interceptors.request.use((config) => {
  const { token } = useAuthStore.getState();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/** 백엔드 표준 API 응답 형식 */
export interface ApiResponse<T = any> {
  success: boolean;
  data: T | null;
  message: string;
  code?: string;
}
