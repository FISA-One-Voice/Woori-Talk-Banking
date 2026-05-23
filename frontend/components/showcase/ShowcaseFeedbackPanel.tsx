import { Pressable, Text } from 'react-native';
import {
  TtsBubble,
  StatusBadge,
  ResultScreen,
  LoadingDots,
  VoiceWaveAnimation,
} from '@/components/feedback';
import { showcaseStyles as styles } from './showcaseStyles';

type TtsVariant = 'default' | 'error' | 'warning';
type ResultType = 'success' | 'error';

interface ShowcaseFeedbackPanelProps {
  ttsVariant: TtsVariant;
  onTtsVariantCycle: () => void;
  voiceActive: boolean;
  onVoiceActiveToggle: () => void;
  resultType: ResultType;
  onResultTypeToggle: () => void;
}

export default function ShowcaseFeedbackPanel({
  ttsVariant,
  onTtsVariantCycle,
  voiceActive,
  onVoiceActiveToggle,
  resultType,
  onResultTypeToggle,
}: ShowcaseFeedbackPanelProps) {
  return (
    <>
      <Text style={styles.sectionLabel}>TtsBubble (탭하여 variant 변경)</Text>
      <Pressable onPress={onTtsVariantCycle}>
        <TtsBubble
          message="50,000원을 엄마 통장으로 보내시겠습니까?"
          variant={ttsVariant}
          autoPlay={false}
        />
        <Text style={styles.hint}>variant: {ttsVariant}</Text>
      </Pressable>

      <Text style={styles.sectionLabel}>StatusBadge</Text>
      <StatusBadge text="음성 인식 중" />
      <StatusBadge text="인증 실패" variant="error" />

      <Text style={styles.sectionLabel}>LoadingDots</Text>
      <LoadingDots />

      <Text style={styles.sectionLabel}>VoiceWaveAnimation</Text>
      <Pressable onPress={onVoiceActiveToggle}>
        <VoiceWaveAnimation isActive={voiceActive} />
        <Text style={styles.hint}>isActive: {String(voiceActive)} (탭하여 토글)</Text>
      </Pressable>

      <Text style={styles.sectionLabel}>ResultScreen (탭하여 타입 변경)</Text>
      <Pressable onPress={onResultTypeToggle}>
        <ResultScreen
          type={resultType}
          label={resultType === 'success' ? '이체 완료' : '이체 실패'}
          subtitle={resultType === 'success' ? '50,000원이 전송되었습니다' : '잔액이 부족합니다'}
        />
        <Text style={styles.hint}>type: {resultType}</Text>
      </Pressable>
    </>
  );
}
