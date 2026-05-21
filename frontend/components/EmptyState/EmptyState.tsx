// =============================================================================
// frontend/components/EmptyState/EmptyState.tsx
//
// [이 컴포넌트의 역할]
// 목록이 비어 있을 때 표시하는 안내 화면입니다.
// 이벤트·거래내역·검색 결과 등 모든 "빈 목록" 상황에서 재사용합니다.
//
// [사용 예시 - 화면 파일에서]
// import EmptyState from '@/components/EmptyState';
// {events.length === 0 && (
//   <EmptyState message="현재 진행 중인 이벤트가 없습니다." icon="📋" />
// )}
//
// [디자이너 작성 · Tech Lead 주석 추가]
// =============================================================================

import { StyleSheet, Text, View } from 'react-native';

import { COLORS, FONT_SIZES } from '@/constants/theme';

// Props: message 와 icon 모두 선택(?)이므로 넘기지 않아도 기본값이 표시됩니다.
type EmptyStateProps = {
  message?: string; // 안내 문구 (기본값: '이벤트가 없습니다')
  icon?: string;    // 이모지 아이콘 (기본값: '📭')
};

export default function EmptyState({
  message = '이벤트가 없습니다',
  icon = '📭',
}: EmptyStateProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.icon}>{icon}</Text>
      <Text style={styles.message}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
    backgroundColor: COLORS.background,
  },
  icon: {
    fontSize: 48,
    marginBottom: 16,
  },
  message: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
  },
});
