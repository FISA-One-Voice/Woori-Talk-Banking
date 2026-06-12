export type AutoTransferStep =
  | 'input-alias'
  | 'input-amount'
  | 'input-cycle'
  | 'input-day'
  | 'confirm'
  | 'asv-pending'
  | 'cancel-input-recipient'
  | 'cancel-confirm';

export type AutoTransferPhase = 'voice-guide' | 'slot-filling' | 'list-view';

/**
 * pending_action / 슬롯 / ASV 상태로 현재 화면 Phase를 결정한다.
 * - list-view : pending 없음 → 자동이체 목록 조회 화면
 * - voice-guide: pending 있고 슬롯 미수집 → TTS 안내 대기
 * - slot-filling: 슬롯 수집 중 또는 ASV 인증 대기
 */
export function resolveAutoTransferPhase(
  pendingAction: string | null | undefined,
  hasSlots: boolean,
  awaitingAsv: boolean,
): AutoTransferPhase {
  if (awaitingAsv || hasSlots) return 'slot-filling';
  if (!pendingAction) return 'list-view';
  return 'voice-guide';
}

export function resolveAutoTransferStep(
  slots: Record<string, unknown>,
  awaitingAsv: boolean,
  pendingAction?: string | null,
): AutoTransferStep {
  if (awaitingAsv) return 'asv-pending';

  if (pendingAction === 'cancel_auto_transfer') {
    if (!slots.recipient) return 'cancel-input-recipient';
    return 'cancel-confirm';
  }

  if (!slots.recipient) return 'input-alias';
  if (!slots.amount)    return 'input-amount';
  if (!slots.cycle)     return 'input-cycle';
  const cycle = slots.cycle as string;
  const isMonthly = cycle === 'monthly' || cycle === '매월' || cycle === '매달';
  const isWeekly  = cycle === 'weekly'  || cycle === '매주';
  if (isMonthly && !slots.scheduled_day)       return 'input-day';
  if (isWeekly  && slots.scheduled_dow == null) return 'input-day';
  return 'confirm';
}

/** 단계 → StepIndicator current 값 */
export const STEP_INDEX: Record<AutoTransferStep, number> = {
  'input-alias':  0,
  'input-amount': 1,
  'input-cycle':  2,
  'input-day':    3,
  'confirm':      4,
  'asv-pending':  4,
  'cancel-input-recipient': 0,
  'cancel-confirm':         1,
};

export const STEP_TOTAL = 5;
export const CANCEL_STEP_TOTAL = 2;

export const DOW_LABEL = ['월', '화', '수', '목', '금', '토', '일'];

export function formatAmount(amount: unknown): string {
  if (typeof amount !== 'number') return String(amount ?? '');
  return `${amount.toLocaleString('ko-KR')}원`;
}

export function formatSchedule(slots: Record<string, unknown>): string {
  const cycle = slots.cycle as string;
  const isMonthly = cycle === 'monthly' || cycle === '매월' || cycle === '매달';
  const isWeekly = cycle === 'weekly' || cycle === '매주';
  if (isMonthly) return `매월 ${slots.scheduled_day}일`;
  if (isWeekly) {
    const dow = slots.scheduled_dow ?? slots.scheduled_day;
    return `매주 ${DOW_LABEL[dow as number]}요일`;
  }
  return '';
}
