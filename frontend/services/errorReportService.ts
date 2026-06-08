import axios, { AxiosError } from 'axios';
import { useAuthStore } from '@/store/authStore';

const BASE_URL = process.env['EXPO_PUBLIC_API_BASE_URL'] ?? 'http://localhost:8000';

interface ClientErrorPayload {
  feature: string;
  error_type: 'timeout' | 'network' | 'http_4xx' | 'http_5xx' | 'unknown';
  error_message: string;
  url?: string;
  method?: string;
  status_code?: number;
}

export function classifyAxiosError(error: AxiosError): ClientErrorPayload['error_type'] {
  if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) return 'timeout';
  if (!error.response) return 'network';
  if (error.response.status >= 500) return 'http_5xx';
  if (error.response.status >= 400) return 'http_4xx';
  return 'unknown';
}

export async function reportClientError(
  feature: string,
  error: unknown,
): Promise<void> {
  const token = useAuthStore.getState().token;
  if (!token) return; // 미인증 상태면 리포트 불가

  let payload: ClientErrorPayload;

  if (axios.isAxiosError(error)) {
    payload = {
      feature,
      error_type: classifyAxiosError(error),
      error_message: error.message,
      url: error.config?.url ?? undefined,
      method: error.config?.method?.toUpperCase() ?? undefined,
      status_code: error.response?.status ?? undefined,
    };
  } else {
    payload = {
      feature,
      error_type: 'unknown',
      error_message: error instanceof Error ? error.message : String(error),
    };
  }

  try {
    await axios.post(`${BASE_URL}/api/client-errors/`, payload, {
      headers: { Authorization: `Bearer ${token}` },
      timeout: 5000,
    });
  } catch {
    // 리포트 실패는 무시 (무한루프 방지)
  }
}
