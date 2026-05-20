// constants/theme.ts

export const COLORS = {
  // 기본 배경 및 카드
  background: '#111111', // --bg: 메인 검은색 배경
  surface: '#1A1A1A', // --bg2: 카드 및 박스 영역
  surfaceLight: '#222222', // --bg3: 메뉴 및 구분선용 옅은 배경
  border: '#2A2A2A', // --border: 테두리선

  // ⚠️ 고대비 핵심 노란색 (시각장애인/저시력자 시인성 확보)
  highlightYellow: '#FFD600', // --y: 메인 옐로우
  yellowBg: '#191900', // --ybg: TTS 말풍선 및 마이크 링 배경
  yellowBorder: '#2D2800', // --ybdr: 옐로우 테두리

  // 흑백 그라데이션 (폰트 및 아이콘용)
  textMain: '#FFFFFF', // --w: 순수 흰색 메인 텍스트
  grayLight: '#AAAAAA', // --g1: 서브 텍스트
  grayMedium: '#777777', // --g2: 힌트/보조 텍스트
  grayDark: '#555555', // --g3: 배지/상태바 텍스트
  grayMuted: '#333333', // --g4: 비활성/플레이스홀더
  grayDeep: '#252525', // --g5: 입력 박스 테두리

  // 상태 알림 색상
  success: '#4CAF50', // --ok: 성공 (초록)
  error: '#E24B4A', // --err: 에러/위험 (빨강)
  warning: '#EF9F27', // --warn: 경고 (주황)
};

export const FONT_SIZES = {
  title: 44, // 큰 금액 / 최상위 타이틀 (목업 반영)
  button: 28, // 🌟 버튼 내부 글자 크기 (터치 및 가독성 확보)
  body: 24, // 일반 본문 / 계좌번호
  ttsAnnouncement: 24, // 🎙️ TTS 음성 안내 텍스트
  caption: 20, // 하단 보조 힌트 / 캡션 텍스트
};

export const LAYOUT = {
  paddingMedium: 14, // 목업 .sc 클래스 기준 좌우 여백
  cardPadding: 12, // 목업 박스 기본 내부 패딩
  borderRadius: 9, // --btnY, .ibox 등 컴포넌트 라운딩 기본값
  cardRadius: 28, // .phone 메인 프레임 라운딩
};
