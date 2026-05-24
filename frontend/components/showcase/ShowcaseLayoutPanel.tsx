import { Pressable, Text, View } from 'react-native';
import { AppScreenHeader, TopBar, TabBar, StepIndicator } from '@/components/layout';
import { showcaseStyles as styles } from './showcaseStyles';

type Tab = 'home' | 'history' | 'alarm' | 'profile';

interface ShowcaseLayoutPanelProps {
  step: number;
  onStepChange: () => void;
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
}

export default function ShowcaseLayoutPanel({
  step,
  onStepChange,
  activeTab,
  onTabChange,
}: ShowcaseLayoutPanelProps) {
  return (
    <>
      <Text style={styles.sectionLabel}>AppScreenHeader (홈 상단)</Text>
      <AppScreenHeader />

      <Text style={styles.sectionLabel}>TopBar · logo</Text>
      <TopBar variant="logo" />

      <Text style={styles.sectionLabel}>TopBar · action</Text>
      <TopBar variant="action" actionLabel="설정" onAction={() => alert('설정')} />

      <Text style={styles.sectionLabel}>StepIndicator (탭하여 단계 변경)</Text>
      <Pressable onPress={onStepChange}>
        <StepIndicator total={4} current={step} />
        <Text style={styles.hint}>현재 단계: {step} / 4</Text>
      </Pressable>

      <Text style={styles.sectionLabel}>TabBar</Text>
      <TabBar activeTab={activeTab} onTabChange={onTabChange} />
    </>
  );
}
