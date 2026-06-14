/** 카테고리별 시각화 테마 — 다크 배경 고대비 색상 기준. */

export interface CategoryTheme {
  /** 바 차트 채움 색상 */
  color: string;
  /** PNG 아이콘 */
  icon: number;
}

const CATEGORY_MAP: Record<string, CategoryTheme> = {
  식비:    { color: '#FF6B6B', icon: require('../icon-yellow/food.png') },
  교통:    { color: '#4ECDC4', icon: require('../icon-yellow/transport.png') },
  쇼핑:    { color: '#45B7D1', icon: require('../icon-yellow/shopping.png') },
  생활비:  { color: '#45B7D1', icon: require('../icon-yellow/living.png') },
  문화생활: { color: '#96CEB4', icon: require('../icon-yellow/culture.png') },
  의료비:  { color: '#88D8B0', icon: require('../icon-yellow/medical.png') },
  의료:    { color: '#88D8B0', icon: require('../icon-yellow/medical.png') },
  금융:    { color: '#FFEAA7', icon: require('../icon-yellow/finance.png') },
  카페:    { color: '#DEB887', icon: require('../icon-yellow/cafe.png') },
  통신:    { color: '#B8B8FF', icon: require('../icon-yellow/telecom.png') },
  가족:    { color: '#FFB347', icon: require('../icon-yellow/family.png') },
  기타:    { color: '#DDA0DD', icon: require('../icon-yellow/etc.png') },
};

const DEFAULT_THEME: CategoryTheme = { color: '#AAAAAA', icon: require('../icon-yellow/etc.png') };

/**
 * 카테고리명으로 색상·아이콘 테마를 반환한다.
 * 미등록 카테고리는 DEFAULT_THEME으로 폴백.
 */
export function getCategoryTheme(category: string): CategoryTheme {
  return CATEGORY_MAP[category] ?? DEFAULT_THEME;
}
