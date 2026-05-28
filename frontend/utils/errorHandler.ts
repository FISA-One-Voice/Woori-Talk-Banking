const ERROR_MESSAGES: Record<string, string> = {
  TOKEN_INVALID: '로그인이 만료되었습니다. 다시 로그인해 주세요.',
  STT_FAILED: '음성을 인식하지 못했습니다. 다시 말씀해 주세요.',
  SERVICE_UNAVAILABLE: '음성 서비스를 일시적으로 이용할 수 없습니다. 잠시 후 다시 시도해 주세요.',
  VOICE_AUDIO_TOO_LARGE: '녹음 파일이 너무 큽니다. 더 짧게 말씀해 주세요.',
  VOICE_AUDIO_INVALID_FORMAT: '지원하지 않는 오디오 형식입니다. 다시 시도해 주세요.',
  VOICE_AUDIO_TOO_LONG: '녹음 시간이 너무 깁니다. 더 짧게 말씀해 주세요.',
  INVALID_REQUEST: '잘못된 요청입니다. 다시 시도해 주세요.',
  ASV_SERVER_ERROR: '화자 인증 서버에 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
  ASV_NOT_ENROLLED: '음성 인증 등록이 필요합니다. 관리자에게 문의해 주세요.',
  ASV_TIMEOUT: '화자 인증 서버 응답이 지연되고 있습니다. 잠시 후 다시 시도해 주세요.',
  MICROPHONE_PERMISSION_DENIED: '마이크 권한이 필요합니다. 설정에서 마이크 접근을 허용해 주세요.',
  VOICE_PROCESSING_ERROR: '음성 처리 중 오류가 발생했습니다. 다시 시도해 주세요.',
};

/**
 * 백엔드 에러 코드를 한국어 TTS 안내 문구로 변환합니다.
 * 알 수 없는 코드는 기본 메시지를 반환합니다.
 */
export function getTtsMessage(code: string): string {
  return ERROR_MESSAGES[code] ?? '오류가 발생했습니다. 잠시 후 다시 시도해 주세요.';
}
