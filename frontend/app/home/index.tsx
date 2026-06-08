import { useState } from 'react';
import { SafeAreaView, ScrollView, StyleSheet, Text, View } from 'react-native';
import { AppScreenHeader, TabBar } from '@/components/layout';
import { VoiceQuickMenuGrid } from '@/components/display';
import { TtsBubble } from '@/components/feedback';
import { HomeVoiceSection } from '@/components/input';
import {
  HOME_MENU_ITEMS,
  HOME_TTS_MESSAGE,
  TAB_PLACEHOLDER,
  type HomeTab,
} from '@/constants/homeMenu';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import { navigateHomeMenu } from '@/utils/navigateHomeMenu';

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
  const [tab, setTab] = useState<HomeTab>('home');

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.body}>
        <ScrollView
          style={styles.scroll}
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
        >
          {tab === 'home' ? (
            <HomeMainContent />
          ) : (
            <View style={styles.placeholder}>
              <Text style={styles.placeholderText}>{TAB_PLACEHOLDER[tab]}</Text>
            </View>
          )}
        </ScrollView>
        <TabBar activeTab={tab} onTabChange={setTab} />
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
