import { useState } from 'react';
import { Pressable, SafeAreaView, ScrollView, StyleSheet, Text, View } from 'react-native';
import { router } from 'expo-router';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import { TopBar } from '@/components/layout';
import {
  ShowcaseDisplayPanel,
  ShowcaseFeedbackPanel,
  ShowcaseInputPanel,
  ShowcaseLayoutPanel,
} from '@/components/showcase';

type Section = 'layout' | 'display' | 'feedback' | 'input';

const SECTIONS: { key: Section; label: string }[] = [
  { key: 'layout', label: 'Layout' },
  { key: 'display', label: 'Display' },
  { key: 'feedback', label: 'Feedback' },
  { key: 'input', label: 'Input' },
];

const MIC_STATES = ['idle', 'listening', 'error', 'warning'] as const;
const TTS_VARIANTS = ['default', 'error', 'warning'] as const;

export default function ShowcaseScreen() {
  const [section, setSection] = useState<Section>('layout');
  const [activeTab, setActiveTab] = useState<'home' | 'history' | 'alarm' | 'profile'>('home');
  const [step, setStep] = useState(2);
  const [micIndex, setMicIndex] = useState(0);
  const [ttsIndex, setTtsIndex] = useState(0);
  const [voiceActive, setVoiceActive] = useState(true);
  const [resultType, setResultType] = useState<'success' | 'error'>('success');
  const [pinResult, setPinResult] = useState<string | null>(null);

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.topBarWrap}>
        <TopBar variant="back" title="컴포넌트 쇼케이스" onBack={() => router.back()} />
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.tabRow}
        contentContainerStyle={styles.tabRowContent}
      >
        {SECTIONS.map(({ key, label }) => (
          <Pressable
            key={key}
            style={[styles.tab, section === key && styles.tabActive]}
            onPress={() => setSection(key)}
          >
            <Text style={[styles.tabText, section === key && styles.tabTextActive]}>{label}</Text>
          </Pressable>
        ))}
      </ScrollView>

      <ScrollView
        style={styles.content}
        contentContainerStyle={styles.contentPadding}
        keyboardShouldPersistTaps="handled"
      >
        {section === 'layout' && (
          <ShowcaseLayoutPanel
            step={step}
            onStepChange={() => setStep((s) => (s % 4) + 1)}
            activeTab={activeTab}
            onTabChange={setActiveTab}
          />
        )}
        {section === 'display' && <ShowcaseDisplayPanel />}
        {section === 'feedback' && (
          <ShowcaseFeedbackPanel
            ttsVariant={TTS_VARIANTS[ttsIndex]}
            onTtsVariantCycle={() => setTtsIndex((i) => (i + 1) % TTS_VARIANTS.length)}
            voiceActive={voiceActive}
            onVoiceActiveToggle={() => setVoiceActive((v) => !v)}
            resultType={resultType}
            onResultTypeToggle={() => setResultType((t) => (t === 'success' ? 'error' : 'success'))}
          />
        )}
        {section === 'input' && (
          <ShowcaseInputPanel
            micState={MIC_STATES[micIndex]}
            onMicStateCycle={() => setMicIndex((i) => (i + 1) % MIC_STATES.length)}
            pinResult={pinResult}
            onPinComplete={setPinResult}
          />
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  topBarWrap: {
    paddingHorizontal: LAYOUT.paddingMedium,
  },
  tabRow: {
    borderBottomWidth: 0.5,
    borderBottomColor: COLORS.surfaceLight,
    flexGrow: 0,
  },
  tabRowContent: {
    paddingHorizontal: LAYOUT.paddingMedium,
    paddingVertical: 8,
    gap: 8,
  },
  tab: {
    paddingVertical: 6,
    paddingHorizontal: 16,
    borderRadius: 20,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  tabActive: {
    backgroundColor: COLORS.highlightYellow,
    borderColor: COLORS.highlightYellow,
  },
  tabText: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayLight,
  },
  tabTextActive: {
    color: COLORS.background,
    fontWeight: '700',
  },
  content: {
    flex: 1,
  },
  contentPadding: {
    padding: LAYOUT.paddingMedium,
    paddingBottom: 40,
  },
});
