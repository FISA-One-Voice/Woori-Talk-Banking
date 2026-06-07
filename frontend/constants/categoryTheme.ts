/** 카테고리별 시각화 테마 — 다크 배경 고대비 색상 기준. */

export interface CategoryTheme {
  /** 바 차트 채움 색상 */
  color: string;
  /** 유니코드 이모지 아이콘 */
  icon: string;
}

const CATEGORY_MAP: Record<string, CategoryTheme> = {
  식비: { color: '#FF6B6B', icon: '🍚' },
  교통: { color: '#4ECDC4', icon: '🚌' },
  쇼핑: { color: '#45B7D1', icon: '🛍️' },
  문화생활: { color: '#96CEB4', icon: '🎬' },
  의료비: { color: '#88D8B0', icon: '🏥' },
  의료: { color: '#88D8B0', icon: '🏥' },
  금융: { color: '#FFEAA7', icon: '💳' },
  카페: { color: '#DEB887', icon: '☕' },
  통신: { color: '#B8B8FF', icon: '📱' },
  기타: { color: '#DDA0DD', icon: '📦' },
};

const DEFAULT_THEME: CategoryTheme = { color: '#AAAAAA', icon: '📌' };

/**
 * 카테고리명으로 색상·아이콘 테마를 반환한다.
 * 미등록 카테고리는 DEFAULT_THEME으로 폴백.
 */
export function getCategoryTheme(category: string): CategoryTheme {
  return CATEGORY_MAP[category] ?? DEFAULT_THEME;
}
