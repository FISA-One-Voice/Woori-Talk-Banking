import { ResultScreen } from '@/components/feedback';
import { ActionButton } from '@/components/display';
import { COLORS, FONT_SIZES } from '@/constants/theme';
import { getTtsMessage } from '@/utils/errorHandler';
import { StyleSheet, Text } from 'react-native';

interface CompleteErrorViewProps {
  onGoHome: () => void;
}

export function CompleteErrorView({ onGoHome }: CompleteErrorViewProps) {
  return (
    <>
      <ResultScreen type="error" label="메모 저장 실패" />
      <Text style={styles.hint}>{getTtsMessage('INTERNAL_ERROR')}</Text>
      <ActionButton label="홈으로 돌아가기" variant="outline" onPress={onGoHome} />
    </>
  );
}

const styles = StyleSheet.create({
  hint: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
    lineHeight: 24,
  },
});
