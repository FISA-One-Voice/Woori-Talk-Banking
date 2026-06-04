/** 확인(네/아니오) 대기 시 화면·TTS 공통 문구 — 백엔드 CONFIRM_YES_NO_SUFFIX와 동기화 */
export const YES_NO_CONFIRM_INSTRUCTION = '네 또는 아니오라고 말씀하시거나, 수정사항을 말씀해 주세요.';

/** 이체 실패 후 홈 이동 TTS — 백엔드 TRANSFER_FAILED_HOME_SUFFIX와 동기화 */
export const TRANSFER_FAILED_HOME_SUFFIX = ' 홈 화면으로 이동합니다.';

export function needsYesNoVoicePrompt(data: {
  awaiting_confirmation?: boolean;
  awaiting_transfer_clarification?: boolean;
}): boolean {
  return Boolean(
    data.awaiting_confirmation || data.awaiting_transfer_clarification,
  );
}

export function ttsIncludesYesNoPrompt(text: string): boolean {
  const compact = text.replace(/\s/g, '');
  return compact.includes('아니오') || compact.includes('아니요');
}
