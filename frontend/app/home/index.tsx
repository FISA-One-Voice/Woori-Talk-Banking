import { SafeAreaView, ScrollView, StyleSheet, View } from 'react-native';
import { useRouter } from 'expo-router';
import { AppScreenHeader, TabBar } from '@/components/layout';
import { VoiceQuickMenuGrid } from '@/components/display';
import { TtsBubble } from '@/components/feedback';
import { HomeVoiceSection } from '@/components/input';
import {
  HOME_MENU_ITEMS,
  HOME_TTS_MESSAGE,
} from '@/constants/homeMenu';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import { navigateHomeMenu } from '@/utils/navigateHomeMenu';
import { useAuthStore } from '@/store/authStore';

function HomeMainContent() {
  return (
    <>
      <AppScreenHeader />
      <TtsBubble message={HOME_TTS_MESSAGE} autoPlay={false} />
      <HomeVoiceSection onMicPress={() => {}} />
      <VoiceQuickMenuGrid
        items={HOME_MENU_ITEMS.map((item) => ({
          icon: item.icon,
          label: item.label,
          voiceHint: item.voiceHint,
          onPress: () => navigateHomeMenu(item.label, item.route),
        }))}
      />
    </>
  );
}

export default function HomeScreen() {
  const router = useRouter();
  const clearTokens = useAuthStore((s) => s.clearTokens);

  function handleLogout() {
    clearTokens();
    router.replace('/login');
  }

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.body}>
        <ScrollView
          style={styles.scroll}
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
        >
          <HomeMainContent />
        </ScrollView>
        <TabBar onLogout={handleLogout} />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  body: {
    flex: 1,
    paddingHorizontal: LAYOUT.paddingMedium,
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 12,
  },
  placeholder: {
    flex: 1,
    minHeight: 200,
    justifyContent: 'center',
    alignItems: 'center',
    padding: LAYOUT.paddingMedium,
  },
  placeholderText: {
    fontSize: FONT_SIZES.body,
    color: COLORS.grayMedium,
    textAlign: 'center',
    lineHeight: 36,
  },
});
