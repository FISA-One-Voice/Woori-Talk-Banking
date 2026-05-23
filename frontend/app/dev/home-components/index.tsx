import { SafeAreaView, ScrollView, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { AppScreenHeader, TopBar } from '@/components/layout';
import { VoiceQuickMenuGrid } from '@/components/display';
import { TtsBubble } from '@/components/feedback';
import { HomeVoiceSection } from '@/components/input';
import { HOME_MENU_ITEMS, HOME_TTS_MESSAGE } from '@/constants/homeMenu';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';

const SAMPLE_MENU = HOME_MENU_ITEMS.map((item) => ({
  ...item,
  onPress: () => alert(`${item.label} 탭`),
}));

export default function HomeComponentsTestScreen() {
  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.pad}>
        <TopBar variant="back" title="홈 UI 컴포넌트" onBack={() => router.back()} />
        <ScrollView contentContainerStyle={styles.scroll}>
          <Text style={styles.sectionLabel}>AppScreenHeader</Text>
          <AppScreenHeader />

          <Text style={styles.sectionLabel}>TtsBubble (홈 문구)</Text>
          <TtsBubble message={HOME_TTS_MESSAGE} autoPlay={false} />

          <Text style={styles.sectionLabel}>HomeVoiceSection</Text>
          <HomeVoiceSection onMicPress={() => alert('마이크 탭')} />

          <Text style={styles.sectionLabel}>VoiceQuickMenuGrid</Text>
          <VoiceQuickMenuGrid items={SAMPLE_MENU} />
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
    paddingHorizontal: LAYOUT.paddingMedium,
  },
  scroll: {
    paddingBottom: 24,
  },
  sectionLabel: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
    marginTop: 16,
    marginBottom: 8,
  },
});
