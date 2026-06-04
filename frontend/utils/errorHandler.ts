// voice router가 AppError를 VoiceResponseData(audio)로 변환해 반환하므로
// 백엔드 에러 코드 → 텍스트 매핑은 불필요.
// 여기서는 백엔드에 도달하지 못하는 순수 클라이언트 에러만 관리한다.
const CLIENT_ONLY_ERRORS: Record<string, string> = {
  MICROPHONE_PERMISSION_DENIED: '마이크 권한이 필요합니다.',
  NETWORK_ERROR: '인터넷 연결을 확인해 주세요.',
  TTS_SERVICE_UNAVAILABLE: '음성 서비스에 문제가 있습니다.',
};

const FALLBACK = '오류가 발생했습니다. 잠시 후 다시 시도해 주세요.';

export const getTtsMessage = (code?: string): string =>
  (code && CLIENT_ONLY_ERRORS[code]) ?? FALLBACK;
