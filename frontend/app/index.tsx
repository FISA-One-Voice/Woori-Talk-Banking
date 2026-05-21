import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import { router } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

export default function Index() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>우리톡뱅킹</Text>
      <Text style={styles.subtitle}>개발 메뉴</Text>

      <Pressable style={styles.btn} onPress={() => router.push('/showcase')}>
        <Text style={styles.btnText}>🧩 컴포넌트 쇼케이스</Text>
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
    marginBottom: 48,
  },
  btn: {
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.highlightYellow,
    borderRadius: LAYOUT.borderRadius,
    paddingVertical: 16,
    paddingHorizontal: 32,
  },
  btnText: {
    fontSize: FONT_SIZES.body,
    color: COLORS.highlightYellow,
    fontWeight: '600',
  },
});
