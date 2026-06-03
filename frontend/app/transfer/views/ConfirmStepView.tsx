import { ActionButton, SummaryBox } from '@/components/display';
import { StyleSheet, View } from 'react-native';
import { formatAmount } from '../stepResolver';

interface ConfirmStepViewProps {
  recipientName: string;
  bankName: string;
  amount: number;
  onCancel: () => void;
  onConfirm: () => void;
}

export function ConfirmStepView({
  recipientName,
  bankName,
  amount,
  onCancel,
  onConfirm,
}: ConfirmStepViewProps) {
  const summaryRows = [
    { label: '받는 분', value: recipientName },
    { label: '은행', value: bankName },
    { label: '금액', value: formatAmount(amount), variant: 'yellow' as const },
  ].filter((r) => r.value);

  return (
    <View style={styles.wrap}>
      <SummaryBox rows={summaryRows} />
      <View style={styles.row}>
        <ActionButton label="취소" variant="outline" flex={1} onPress={onCancel} />
        <ActionButton label="확인" flex={2} onPress={onConfirm} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 12 },
  row: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 8,
  },
});
