/**
 * /transfer 화면 내부 단계 — collected_slots·awaiting_asv 기준 (순수 함수).
 * 라우트 이동은 _layout의 navigate_to가 담당한다.
 */

export type TransferStep =
  | 'input-alias'
  | 'input-amount'
  | 'confirm'
  | 'asv-pending';

export function resolveTransferStep(
  slots: Record<string, unknown>,
  awaitingAsv: boolean,
  pendingAction?: string | null,
): TransferStep {
  if (awaitingAsv) return 'asv-pending';

  void pendingAction;

  if (!slots.recipient) return 'input-alias';
  if (!slots.amount) return 'input-amount';
  return 'confirm';
}

export const STEP_INDEX: Record<TransferStep, number> = {
  'input-alias': 0,
  'input-amount': 1,
  confirm: 2,
  'asv-pending': 2,
};

export const STEP_TOTAL = 3;

export function formatAmount(amount: unknown): string {
  if (typeof amount !== 'number') return String(amount ?? '');
  return `${amount.toLocaleString('ko-KR')}원`;
}
