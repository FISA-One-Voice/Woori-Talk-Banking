/**
 * 자동이체 슬롯 상태 → 현재 단계 결정 로직.
 *
 * voice-pipeline-flow.md 기준 슬롯 수집 순서:
 *   alias → amount → cycle → scheduled_day(monthly) / scheduled_dow(weekly)
 *
 * _layout.tsx 가 내려주는 collected_slots 와 awaiting_asv_audio 를 받아
 * 화면에 표시할 서브스텝을 결정합니다.
 */

export type AutoTransferStep =
  | 'input-alias'
  | 'input-amount'
  | 'input-cycle'
  | 'input-day'
  | 'confirm'
  | 'asv-pending';

export function resolveAutoTransferStep(
  slots: Record<string, unknown>,
  awaitingAsv: boolean,
): AutoTransferStep {
  if (awaitingAsv)          return 'asv-pending';
  if (!slots.alias)         return 'input-alias';
  if (!slots.amount)        return 'input-amount';
  if (!slots.cycle)         return 'input-cycle';
  const cycle = slots.cycle as string;
  if (cycle === 'monthly' && !slots.scheduled_day)      return 'input-day';
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
};

export const STEP_TOTAL = 5;

export const DOW_LABEL = ['월', '화', '수', '목', '금', '토', '일'];

export function formatAmount(amount: unknown): string {
  if (typeof amount !== 'number') return String(amount ?? '');
  return `${amount.toLocaleString('ko-KR')}원`;
}

export function formatSchedule(slots: Record<string, unknown>): string {
  const cycle = slots.cycle as string;
  if (cycle === 'monthly') return `매월 ${slots.scheduled_day}일`;
  if (cycle === 'weekly') {
    const dow = slots.scheduled_dow as number;
    return `매주 ${DOW_LABEL[dow]}요일`;
  }
  return '';
}
