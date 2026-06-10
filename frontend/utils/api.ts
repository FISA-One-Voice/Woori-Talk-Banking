import { useAuthStore } from '@/store/authStore';
import axios from 'axios';
import { reportClientError } from '@/services/errorReportService';

// URL 경로에서 feature 이름 추출: /api/transfer/... → "transfer"
function extractFeature(url: string | undefined): string {
  if (!url) return 'unknown';
  const match = url.match(/\/api\/([^/?]+)/);
  return match?.[1] ?? 'unknown';
}

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

if (__DEV__ && !process.env['EXPO_PUBLIC_API_BASE_URL']) {
  console.warn(
    '[api.ts] EXPO_PUBLIC_API_BASE_URL 환경변수가 설정되지 않았습니다.\n' +
      'frontend/.env.example 을 복사해 frontend/.env 를 만들고 본인 IP를 입력하세요.',
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
// 1. Request 인터셉터: 나가는 요청 헤더에 톨게이트처럼 토큰 부착
apiClient.interceptors.request.use((config) => {
  const { token } = useAuthStore.getState();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 2. Response 인터셉터: 만료된 토큰(401) 응답을 가로채서 새 토큰으로 자동 재요청 (Silent Refresh)
apiClient.interceptors.response.use(
  (response) => response, // 성공한 응답은 그대로 패스
  async (error) => {
    const originalRequest = error.config;

    // 백엔드에서 401(Unauthorized) 에러를 뱉었고, 아직 재요청을 시도하지 않은 상태라면?
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true; // 무한 루프 방지용 플래그

      const { refreshToken, setTokens, clearTokens } = useAuthStore.getState();

      if (refreshToken) {
        try {
          // 백엔드에 리프레시 토큰을 보내서 새 토큰 발급 요청 (axios 날것으로 호출)
          const response = await axios.post(`${BASE_URL}/api/users/refresh`, {
            refreshToken: refreshToken,
          });

          if (response.data.success) {
            const newAccessToken = response.data.data.accessToken;
            const newRefreshToken = response.data.data.refreshToken || refreshToken;

            // 새로 발급받은 토큰들을 전역 금고에 갱신
            setTokens(newAccessToken, newRefreshToken);

            // 실패했던 원래 요청의 헤더를 새 토큰으로 교체하고 다시 전송! (마치 에러가 없었던 것처럼)
            originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
            return apiClient(originalRequest);
          }
        } catch (refreshError) {
          // 리프레시 토큰마저 만료되었거나 에러가 났다면 강제 로그아웃
          clearTokens();
        }
      } else {
        clearTokens();
      }
    }

    // 에러 리포트 (401 silent refresh 이후 재시도 요청, /api/client-errors 자체는 제외)
    const url = error.config?.url ?? '';
    if (!url.includes('/api/client-errors') && !originalRequest._retry) {
      reportClientError(extractFeature(url), error);
    }

    return Promise.reject(error);
  },
);

/** 백엔드 표준 API 응답 형식 */
export interface ApiResponse<T = any> {
  success: boolean;
  data: T | null;
  message: string;
  code?: string;
}
