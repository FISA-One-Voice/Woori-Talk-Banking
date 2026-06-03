/**
 * POST /api/voice 응답 data 필드 타입.
 *
 * 백엔드 shared/voice/schema.py의 VoiceResponseData와 1:1 대응.
 * 필드 추가/변경 시 백엔드 스키마와 반드시 동기화.
 */
export interface VoiceResponseData {
  /** base64 인코딩된 MP3 — 디코딩 후 재생 */
  audio: string;

  /**
   * 이동할 화면 이름 (Expo Router 경로 기준).
   * - "transfer", "auto-transfer", "balance", "event" 등
   * - null이면 현재 화면 유지
   */
  navigate_to: string | null;

  /**
   * 현재까지 수집된 슬롯.
   * 화면 담당자가 stepResolver에서 단계 판단에 사용.
   * 예: { alias: "엄마", amount: 100000 }
   */
  collected_slots: Record<string, unknown>;

  /**
   * 텍스트 확인("네/아니오") 대기 상태.
   * true이면 VoiceStatusOverlay에 확인 대기 UI 표시.
   */
  awaiting_confirmation: boolean;

  /**
   * 음성 보안 인증(ASV) 대기 상태.
   * true이면 다음 음성 입력이 명령이 아닌 화자 인증용으로 처리됨.
   * transfer, auto_transfer 확인 후에만 true로 설정됨.
   */
  awaiting_asv_audio: boolean;

  /**
   * 이체 직후 메모 제안 응답 대기.
   * true이면 VoiceStatusOverlay에 메모 안내 표시.
   */
  awaiting_memo_decision: boolean;

  /**
   * 전화·계좌만 말한 뒤 송금 여부(네/아니오) 확인 대기.
   */
  awaiting_transfer_clarification?: boolean;

  /**
   * STT 변환 결과 텍스트 (사용자가 말한 내용).
   * 정상 흐름에서만 채워지며 ASV 인증 흐름에서는 null.
   */
  transcript: string | null;

  /**
   * 현재 진행 중인 액션 이름.
   * - "auto_transfer": 자동이체 등록 흐름
   * - "cancel_auto_transfer": 자동이체 해지 흐름
   * - null이면 액션 없음
   */
  pending_action: string | null;
}

/**
 * POST /api/voice 표준 봉투 응답 타입.
 *
 * 성공: success=true, data=VoiceResponseData, message=TTS 원문
 * 실패: success=false, data=null, message=에러 설명, code=에러 코드
 */
export type VoiceResponse =
  | {
      success: true;
      data: VoiceResponseData;
      message: string;
    }
  | {
      success: false;
      data: null;
      message: string;
      code: string;
    };
