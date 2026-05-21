// =============================================================================
// frontend/components/SuccessScreen/SuccessScreen.tsx
//
// [이 컴포넌트의 역할]
// 이벤트 참여 완료 등 성공 결과를 보여주는 전체 화면 컴포넌트입니다.
// 확인 버튼을 누르면 이전 화면이나 홈으로 돌아갑니다.
//
// [사용 예시 - 화면 파일(app/event/[id].tsx)에서]
// import SuccessScreen from '@/components/SuccessScreen';
// {isSuccess && (
//   <SuccessScreen
//     eventName={event.title}
//     onConfirm={() => router.back()}
//   />
// )}
//
// [디자이너 작성 · Tech Lead 주석 추가]
// =============================================================================

import { Pressable, StyleSheet, Text, View } from 'react-native';

import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';

// Props: 이 컴포넌트가 부모(화면)로부터 받는 값들의 형태 정의
type SuccessScreenProps = {
  eventName: string;   // 참여한 이벤트 이름 (필수)
  message?: string;    // 추가 안내 문구 (선택, 기본값: '성공적으로 참여했습니다')
  onConfirm: () => void; // 확인 버튼을 눌렀을 때 실행할 함수 (필수)
};

export default function SuccessScreen({
  eventName,
  message = '성공적으로 참여했습니다',
  onConfirm,
}: SuccessScreenProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.icon}>✅</Text>
      <Text style={styles.title}>참여 완료</Text>
      <Text style={styles.eventName}>{eventName}</Text>
      <Text style={styles.message}>{message}</Text>

      <Pressable style={styles.button} onPress={onConfirm}>
        <Text style={styles.buttonText}>확인</Text>
      </Pressable>
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
    fontSize: 64,
    marginBottom: 16,
  },
  title: {
    fontSize: FONT_SIZES.body,
    fontWeight: '700',
    color: COLORS.textMain,
    marginBottom: 8,
  },
  eventName: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMuted,
    marginBottom: 4,
  },
  message: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
    marginBottom: 32,
  },
  button: {
    backgroundColor: COLORS.highlightYellow,
    paddingVertical: 14,
    paddingHorizontal: 48,
    borderRadius: LAYOUT.borderRadius,
  },
  buttonText: {
    color: COLORS.background,
    fontSize: FONT_SIZES.button,
    fontWeight: '600',
  },
});
