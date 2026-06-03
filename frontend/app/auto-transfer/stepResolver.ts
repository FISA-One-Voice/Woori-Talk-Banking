export type AutoTransferStep =
  | 'input-alias'
  | 'input-amount'
  | 'input-cycle'
  | 'input-day'
  | 'confirm'
  | 'asv-pending'
  | 'cancel-input-recipient'
  | 'cancel-confirm';

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
  if (cycle === 'monthly' && !slots.scheduled_day)       return 'input-day';
  if (cycle === 'weekly'  && slots.scheduled_dow == null) return 'input-day';
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
  const isMonthly = cycle === 'monthly' || cycle === '매월';
  const isWeekly = cycle === 'weekly' || cycle === '매주';
  if (isMonthly) return `매월 ${slots.scheduled_day}일`;
  if (isWeekly) {
    const dow = slots.scheduled_dow ?? slots.scheduled_day;
    return `매주 ${DOW_LABEL[dow as number]}요일`;
  }
  return '';
}
