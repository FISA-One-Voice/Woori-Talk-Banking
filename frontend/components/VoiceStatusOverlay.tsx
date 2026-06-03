import { YES_NO_CONFIRM_INSTRUCTION } from '@/constants/voicePrompts';
import { StyleSheet, Text, View } from 'react-native';
import VoiceWaveAnimation from '@/components/feedback/VoiceWaveAnimation';

export type VoiceState =
  | 'idle'
  | 'recording'
  | 'processing'
  | 'awaiting_confirm'
  | 'awaiting_asv'
  | 'awaiting_memo';

const OVERLAY_MESSAGES: Partial<Record<VoiceState, string>> = {
  processing: '처리 중...',
  awaiting_confirm: YES_NO_CONFIRM_INSTRUCTION,
  awaiting_asv: '음성 인증을 위해 말씀해 주세요',
  awaiting_memo: '메모 카테고리를 말씀하거나 건너뛰기라고 하세요',
};

interface Props {
  state: VoiceState;
}

export default function VoiceStatusOverlay({ state }: Props) {
  if (state === 'idle') return null;

  return (
    <View pointerEvents="none" style={styles.container}>
      {state === 'recording' ? (
        <VoiceWaveAnimation isActive />
      ) : (
        <Text style={styles.message}>{OVERLAY_MESSAGES[state]}</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    bottom: 60,
    left: 20,
    right: 20,
    alignItems: 'center',
    backgroundColor: 'rgba(0, 0, 0, 0.75)',
    paddingVertical: 16,
    paddingHorizontal: 24,
    borderRadius: 12,
  },
  message: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
    textAlign: 'center',
  },
});
