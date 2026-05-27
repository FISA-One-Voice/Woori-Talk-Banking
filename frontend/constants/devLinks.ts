export interface DevLinkItem {
  label: string;
  path: string;
}

/** 루트(/)에 없는 개발·검증용 화면만 등록 (홈·앱 진입은 /index 에서 처리) */
export const DEV_LINKS: DevLinkItem[] = [
  { label: '이벤트 구현', path: '/dev/home-event/event' },
  { label: '컴포넌트 쇼케이스', path: '/showcase' },
  { label: '홈 UI 컴포넌트', path: '/dev/home-components' },
];
