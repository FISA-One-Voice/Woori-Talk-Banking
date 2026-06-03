import { useEffect } from 'react';
import { SafeAreaView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { COLORS, FONT_SIZES } from '@/constants/theme';
import { useVoiceResponseStore } from '@/store/voiceResponseStore';
import { formatAmount, formatSchedule } from './stepResolver';

export default function AutoTransferCompleteScreen() {
  const router = useRouter();
  const lastResponse = useVoiceResponseStore((s) => s.lastResponse);
  const slots = lastResponse?.collected_slots ?? {};

  useEffect(() => {
    const timer = setTimeout(() => router.replace('/home'), 3000);
    return () => clearTimeout(timer);
  }, [router]);

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.container}>
        <View style={styles.circle}>
          <Text style={styles.checkIcon}>✓</Text>
        </View>

        <Text style={styles.title}>자동이체 등록 완료</Text>

        {slots.alias && (
          <View style={styles.summaryBox}>
            <SummaryRow label="수취인" value={String(slots.alias)} />
            <SummaryRow label="금액" value={formatAmount(slots.amount)} />
            <SummaryRow label="일정" value={formatSchedule(slots)} />
          </View>
        )}

        <Text style={styles.redirect}>잠시 후 홈으로 이동합니다</Text>
      </View>
    </SafeAreaView>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 24,
    gap: 20,
  },
  circle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    borderWidth: 2.5,
    borderColor: COLORS.success,
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkIcon: {
    fontSize: 40,
    color: COLORS.success,
    fontWeight: '700',
  },
  title: {
    fontSize: FONT_SIZES.button,
    fontWeight: '700',
    color: COLORS.textMain,
  },
  summaryBox: {
    width: '100%',
    backgroundColor: COLORS.surface,
    borderRadius: 12,
    borderWidth: 0.5,
    borderColor: COLORS.border,
    paddingHorizontal: 20,
    paddingVertical: 16,
    gap: 12,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  rowLabel: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayLight,
  },
  rowValue: {
    fontSize: FONT_SIZES.body,
    color: COLORS.textMain,
    fontWeight: '600',
  },
  redirect: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
    marginTop: 8,
  },
});
