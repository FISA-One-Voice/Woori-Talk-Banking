export type HomeTab = 'home' | 'history' | 'alarm' | 'profile';

export interface HomeMenuItem {
  icon: number;
  label: string;
  voiceHint: string;
  route: string | null;
}

/** TODO: 담당 기능 연동 시 route 에 화면 경로 지정 */
export const HOME_MENU_ITEMS: HomeMenuItem[] = [
  { icon: require('../icon-yellow/transfer.png'), label: '이체하기', voiceHint: '"이체해줘"', route: '/transfer' },
  { icon: require('../icon-yellow/asset.png'), label: '내 자산', voiceHint: '"내 자산"', route: '/asset' },
  { icon: require('../icon-yellow/auto-transfer.png'), label: '자동이체', voiceHint: '"자동이체"', route: '/auto-transfer' },
  { icon: require('../icon-yellow/event.png'), label: '이벤트', voiceHint: '"이벤트"', route: '/event' },
];

export const HOME_TTS_MESSAGE = '어떤 업무를 도와드릴까요?';

export const TAB_PLACEHOLDER: Record<Exclude<HomeTab, 'home'>, string> = {
  history: '거래내역 화면 — 담당자 개발 예정',
  alarm: '알림 화면 — 담당자 개발 예정',
  profile: '내 정보 화면 — 담당자 개발 예정',
};
