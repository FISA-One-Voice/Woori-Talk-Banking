import { Pressable, SafeAreaView, ScrollView, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { TopBar } from '@/components/layout';
import { DEV_LINKS } from '@/constants/devLinks';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';

import { useAuthStore } from '@/store/authStore';
import { syncDeviceContactsToBackend } from '@/utils/contactSync';

export default function DevHubScreen() {
  const clearTokens = useAuthStore((state) => state.clearTokens);

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.pad}>
        <TopBar variant="back" title="테스트 허브" onBack={() => router.back()} />
        <ScrollView
          style={styles.scroll}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          <Text style={styles.hint}>
            앱 진입(홈)은 첫 화면의 「앱 진입」을 사용하세요.{'\n'}
            여기는 컴포넌트·API 등 개발용 화면만 모아 둡니다.
          </Text>
          
          <Pressable 
            style={[styles.link, { backgroundColor: '#3f1a1a', borderColor: '#F87171', marginBottom: 8 }]} 
            onPress={() => {
              clearTokens();
              router.replace('/login');
            }}
          >
            <Text style={[styles.linkText, { color: '#F87171' }]}>🗑️ 토큰 및 상태 초기화 (로그아웃)</Text>
          </Pressable>

          <Pressable 
            style={[styles.link, { backgroundColor: COLORS.surfaceLight, borderColor: COLORS.highlightYellow, marginBottom: 16 }]} 
            onPress={syncDeviceContactsToBackend}
          >
            <Text style={[styles.linkText, { color: COLORS.textMain }]}>📱 기기 연락처 동기화 테스트</Text>
          </Pressable>

          {DEV_LINKS.map((item) => (
            <Pressable key={item.path} style={styles.link} onPress={() => router.push(item.path)}>
              <Text style={styles.linkText}>{item.label}</Text>
            </Pressable>
          ))}
        </ScrollView>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  pad: {
    flex: 1,
    padding: LAYOUT.paddingMedium,
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    gap: 10,
    paddingBottom: 28,
  },
  hint: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
    marginBottom: 8,
    lineHeight: 28,
  },
  link: {
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: LAYOUT.borderRadius,
    paddingVertical: 14,
    paddingHorizontal: 16,
  },
  linkText: {
    fontSize: FONT_SIZES.body,
    color: COLORS.highlightYellow,
    fontWeight: '600',
  },
});
