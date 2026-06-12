import { StyleSheet, View } from 'react-native';
import { ResultScreen, TtsBubble } from '@/components/feedback';
import { ActionButton } from '@/components/display';
import { LAYOUT } from '@/constants/theme';

interface TransferFailedViewProps {
  errorMessage: string;
  onGoHome: () => void;
}

/** SCR004-F08 — 송금 실패 (잔액 부족 등) */
export function TransferFailedView({ errorMessage, onGoHome }: TransferFailedViewProps) {
  return (
    <View style={styles.root}>
      <TtsBubble message={errorMessage} variant="error" textAlign="left" />
      <View style={styles.center}>
        <ResultScreen type="error" label="송금 실패" />
      </View>
      <View style={styles.footer}>
        <ActionButton label="홈으로 돌아가기" variant="outline" onPress={onGoHome} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  footer: {
    paddingBottom: LAYOUT.paddingMedium,
  },
});
