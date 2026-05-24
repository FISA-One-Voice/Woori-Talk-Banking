import { router } from 'expo-router';

/** 홈 퀵메뉴 탭 — route 미연결 시 개발 안내만 표시 */
export function navigateHomeMenu(label: string, route: string | null): void {
  if (route) {
    router.push(route);
    return;
  }

  if (__DEV__) {
    alert(
      `「${label}」 기능은 준비 중입니다. app/ 아래에 화면을 추가한 뒤 HOME_MENU_ITEMS.route 를 연결하세요.`,
    );
  }
}
