/** 에이전트 navigate_to ↔ Expo Router 경로 비교 */

export function agentPathFromNavigateTo(navigateTo: string): string {
  if (navigateTo === 'home') return '/home';
  return `/${navigateTo}`;
}

/** 완료·실패 등 이체 플로우 종료 화면 — 송금 입력(/transfer)으로 다시 이동 가능 */
const TRANSFER_LEAF_ROUTES = new Set(['/transfer/failed', '/transfer/complete']);

/**
 * 이미 대상 화면(또는 transfer 하위 경로)에 있으면 replace 하지 않는다.
 * /transfer 위에서 슬롯만 바뀔 때 중복 replace 방지.
 * 단, /transfer/failed·complete 에서는 /transfer·/home 이동을 허용한다.
 */
export function shouldNavigateToRoute(
  currentPath: string,
  navigateTo: string,
): boolean {
  const target = agentPathFromNavigateTo(navigateTo);
  const current = currentPath.replace(/\/$/, '') || '/';
  const normalizedTarget = target.replace(/\/$/, '');

  if (current === normalizedTarget) {
    return false;
  }

  if (
    navigateTo === 'transfer' &&
    (current === '/transfer' || current.startsWith('/transfer/')) &&
    !TRANSFER_LEAF_ROUTES.has(current)
  ) {
    return false;
  }

  if (
    navigateTo === 'auto-transfer' &&
    (current === '/auto-transfer' || current.startsWith('/auto-transfer/'))
  ) {
    return false;
  }

  return true;
}
