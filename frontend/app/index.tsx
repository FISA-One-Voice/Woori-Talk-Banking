import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Redirect, router } from 'expo-router';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';

export default function Index() {
  if (!__DEV__) {
    return <Redirect href="/home" />;
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>우리톡뱅킹</Text>
      <Text style={styles.subtitle}>개발 진입</Text>

      <Pressable style={styles.btn} onPress={() => router.push('/dev')}>
        <Text style={styles.btnText}>🧪 테스트</Text>
      </Pressable>

      <Pressable style={styles.btn} onPress={() => router.push('/showcase')}>
        <Text style={styles.btnText}>🎨 컴포넌트 쇼케이스</Text>
      </Pressable>

      <Pressable style={[styles.btn, styles.btnPrimary]} onPress={() => router.push('/login')}>
        <Text style={[styles.btnText, styles.btnTextDark]}>🔐 로그인 (앱 시작)</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
    justifyContent: 'center',
    alignItems: 'center',
    padding: LAYOUT.paddingMedium,
    gap: 12,
  },
  title: {
    fontSize: FONT_SIZES.title,
    fontWeight: '700',
    color: COLORS.highlightYellow,
    marginBottom: 8,
  },
  subtitle: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
    marginBottom: 36,
  },
  btn: {
    width: '100%',
    maxWidth: 320,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.highlightYellow,
    borderRadius: LAYOUT.borderRadius,
    paddingVertical: 16,
    paddingHorizontal: 32,
    alignItems: 'center',
  },
  btnPrimary: {
    backgroundColor: COLORS.highlightYellow,
    borderColor: COLORS.highlightYellow,
  },
  btnText: {
    fontSize: FONT_SIZES.body,
    color: COLORS.highlightYellow,
    fontWeight: '600',
  },
  btnTextDark: {
    color: COLORS.background,
  },
});
