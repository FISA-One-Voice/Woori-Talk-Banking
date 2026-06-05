/** 에이전트 navigate_to ↔ Expo Router 경로 비교 */

export function agentPathFromNavigateTo(navigateTo: string): string {
  if (navigateTo === 'home') return '/home';
  return `/${navigateTo}`;
}

/**
 * 이미 대상 화면(또는 transfer 하위 경로)에 있으면 replace 하지 않는다.
 * /transfer 위에서 슬롯만 바뀔 때 중복 replace 방지.
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
    (current === '/transfer' || current.startsWith('/transfer/'))
  ) {
    return false;
  }

  if (
    navigateTo === 'auto-transfer' &&
    (current === '/auto-transfer' || current.startsWith('/auto-transfer/'))
  ) {
    return false;
  }

  if (navigateTo === 'asset' && current === '/asset') {
    return false;
  }

  return true;
}
