import { Text } from 'react-native';
import { HomeVoiceSection, MicButton, AccessibleNumKeypad } from '@/components/input';
import { showcaseStyles as styles } from './showcaseStyles';

type MicState = 'idle' | 'listening' | 'error' | 'warning';

interface ShowcaseInputPanelProps {
  micState: MicState;
  onMicStateCycle: () => void;
  pinResult: string | null;
  onPinComplete: (pin: string) => void;
}

export default function ShowcaseInputPanel({
  micState,
  onMicStateCycle,
  pinResult,
  onPinComplete,
}: ShowcaseInputPanelProps) {
  return (
    <>
      <Text style={styles.sectionLabel}>HomeVoiceSection (홈 음성 영역)</Text>
      <HomeVoiceSection micState={micState} onMicPress={onMicStateCycle} />

      <Text style={styles.sectionLabel}>MicButton (탭하여 state 변경)</Text>
      <MicButton state={micState} hint={`상태: ${micState}`} onPress={onMicStateCycle} />

      <Text style={styles.sectionLabel}>AccessibleNumKeypad (4자리)</Text>
      <AccessibleNumKeypad length={4} onComplete={onPinComplete} />
      {pinResult && <Text style={styles.hint}>입력 완료 (마스킹 표시): ••••</Text>}
    </>
  );
}
