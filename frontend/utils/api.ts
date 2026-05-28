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
//
// expo start 실행 시 Expo 가 자동으로 읽습니다. (SDK 49+ 기본 지원)
// frontend/.env 는 .gitignore 에 포함되어 있어 커밋되지 않습니다.
//
// IP 확인:
//   Windows  → PowerShell: ipconfig   (IPv4 주소)
//   Mac/Linux → 터미널: ipconfig getifaddr en0
// =============================================================================

import axios from 'axios';
import { useAuthStore } from '@/store/authStore';

// EXPO_PUBLIC_API_BASE_URL 이 없으면 경고를 출력하고 localhost 를 사용합니다.
// Expo Go(모바일)에서는 localhost 가 동작하지 않으므로 반드시 .env 를 설정하세요.
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

// 요청 인터셉터: 모든 API 요청에 authStore 토큰 자동 첨부
// 각 스토어/화면에서 토큰을 직접 꺼내 헤더에 넣을 필요 없습니다.
apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

/** 백엔드 표준 API 응답 형식 */
export interface ApiResponse<T> {
  success: boolean;
  data: T | null;
  message: string;
  code?: string;
}
