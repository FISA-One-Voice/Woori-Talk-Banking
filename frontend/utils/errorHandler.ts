const MESSAGES: Record<string, string> = {
  ACCOUNT_NOT_FOUND:              '계좌 정보를 불러올 수 없습니다.',
  ACCOUNT_INSUFFICIENT_BALANCE:   '잔액이 부족합니다.',
  ACCOUNT_ALIAS_DUPLICATE:        '이미 사용 중인 계좌 별칭입니다.',
  TX_NOT_FOUND:                   '거래 내역이 없습니다.',
  TX_ALREADY_PROCESSED:           '이미 처리된 거래입니다.',
  TRANSFER_AMOUNT_INVALID:        '송금액을 확인해 주세요.',
  TRANSFER_RECIPIENT_NOT_FOUND:   '수취인 정보를 찾을 수 없습니다.',
  TRANSFER_SESSION_INVALID:       '송금 세션이 만료되었습니다. 다시 시도해 주세요.',
  TRANSFER_IDEMPOTENCY_CONFLICT:  '이미 처리된 송금 요청입니다.',
  RECIPIENT_NOT_FOUND:            '등록된 수취인을 찾을 수 없습니다.',
  RECIPIENT_ALIAS_DUPLICATE:      '이미 사용 중인 수취인 별칭입니다.',
  CONTACT_AMBIGUOUS:              '동일한 이름의 수취인이 여러 명입니다. 계좌번호로 다시 말씀해 주세요.',
  AUTO_ORDER_SCHEDULE_INVALID:    '자동이체 날짜를 다시 확인해 주세요.',
  AUTO_ORDER_TERMS_NOT_AGREED:    '자동이체 약관 동의가 필요합니다.',
  AUTO_ORDER_WITHDRAWAL_PASSWORD_INVALID: '출금 비밀번호가 일치하지 않습니다.',
  AUTO_ORDER_EXECUTION_FAILED:    '자동이체 실행에 실패했습니다.',
  UNAUTHORIZED:                   '로그인이 필요합니다.',
  USER_NOT_FOUND:                 '사용자 정보를 찾을 수 없습니다.',
  TOKEN_INVALID:                  '로그인 세션이 만료되었습니다. 다시 로그인해 주세요.',
  VOICE_AUTH_FAILED:              '음성 인증에 실패했습니다. 다시 시도해 주세요.',
  ASV_CONFIDENCE_LOW:             '목소리가 잘 인식되지 않았습니다. 다시 말씀해 주세요.',
  STT_FAILED:                     '음성 인식에 실패했습니다. 다시 말씀해 주세요.',
  NLU_INTENT_UNRECOGNIZED:        '말씀하신 내용을 이해하지 못했습니다. 다시 말씀해 주세요.',
  INTERNAL_ERROR:                 '서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
  INVALID_REQUEST:                '요청 정보를 다시 확인해 주세요.',
  RATE_LIMIT_EXCEEDED:            '요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.',
  SERVICE_UNAVAILABLE:            '서비스가 일시적으로 중단되었습니다. 잠시 후 다시 시도해 주세요.',
  NETWORK_ERROR:                  '네트워크 연결을 확인해 주세요.',
};

const FALLBACK = '오류가 발생했습니다. 잠시 후 다시 시도해 주세요.';

export const getTtsMessage = (code?: string): string =>
  (code && MESSAGES[code]) ?? FALLBACK;
