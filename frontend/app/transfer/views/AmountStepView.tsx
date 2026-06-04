import { StatusBadge } from '@/components/feedback';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';

const AMOUNT_PRESETS = [10000, 30000, 50000, 100000, 300000, 500000];

interface AmountStepViewProps {
  recipientName: string;
  onSelectAmount: (amount: number) => void;
}

export function AmountStepView({ recipientName, onSelectAmount }: AmountStepViewProps) {
  return (
    <View style={styles.wrap}>
      <StatusBadge text={`${recipientName}님 — 금액 선택`} />
      <View style={styles.amountGrid}>
        {AMOUNT_PRESETS.map((amt) => (
          <TouchableOpacity
            key={amt}
            style={styles.amountBtn}
            onPress={() => onSelectAmount(amt)}
            accessibilityRole="button"
            accessibilityLabel={`${amt.toLocaleString('ko-KR')}원`}
          >
            <Text style={styles.amountText}>{amt.toLocaleString('ko-KR')}원</Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 12 },
  amountGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginTop: 8,
  },
  amountBtn: {
    width: '47%',
    paddingVertical: 18,
    backgroundColor: COLORS.surfaceLight,
    borderRadius: LAYOUT.borderRadius,
    borderWidth: 1,
    borderColor: COLORS.border,
    alignItems: 'center',
  },
  amountText: {
    fontSize: FONT_SIZES.body,
    color: COLORS.textMain,
    fontWeight: '600',
  },
});
