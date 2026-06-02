/** /transfer/complete 터치 UI phase (음성 메모는 에이전트·_layout 담당) */

export type CompletePhase = 'summary' | 'memo_done' | 'error';

export function resolveCompletePhase(localStep: CompletePhase): CompletePhase {
  return localStep;
}
