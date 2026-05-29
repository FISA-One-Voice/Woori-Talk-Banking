export interface DevLinkItem {
  label: string;
  path: string;
}

/** 루트(/)에 없는 개발·검증용 화면만 등록 (홈·앱 진입은 /index 에서 처리) */
export const DEV_LINKS: DevLinkItem[] = [
  { label: '컴포넌트 쇼케이스', path: '/showcase' },
  { label: '홈 UI 컴포넌트', path: '/dev/home-components' },
  { label: '로그인 화면 테스트 (Real API)', path: '/dev/login' },
  { label: '자동이체 화면', path: '/auto-transfer' },
  { label: '자동이체 완료 화면', path: '/auto-transfer/complete' },
];
