export interface DevLinkItem {
  label: string;
  path: string;
}

/** 루트(/)에 없는 개발·검증용 화면만 등록 (홈·앱 진입은 /index 에서 처리) */
export const DEV_LINKS: DevLinkItem[] = [
  { label: '홈 화면', path: '/dev/home' },
  { label: '이벤트', path: '/dev/event' },
  { label: '컴포넌트 쇼케이스', path: '/showcase' },
  { label: '홈 UI 컴포넌트', path: '/dev/home-components' },
  { label: '로그인 화면 테스트 (Real API)', path: '/dev/login' },
  { label: '자동이체 화면', path: '/auto-transfer' },
  { label: '자동이체 완료 화면', path: '/auto-transfer/complete' },
  { label: '송금 화면 (Real API)', path: '/transfer' },
  { label: '송금 완료 화면', path: '/transfer/complete' },
  { label: '송금 실패 (SCR004-F08)', path: '/transfer/failed' },
  { label: '[테스트] 이체 플로우 시나리오', path: '/dev/transfer-test' },
];
