import { AppScreenHeader, StepIndicator } from '@/components/layout';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import { useVoiceResponseStore } from '@/store/voiceResponseStore';
import { apiClient } from '@/utils/api';
import { useEffect } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import {
  CANCEL_STEP_TOTAL,
  formatAmount,
  formatSchedule,
  resolveAutoTransferStep,
  STEP_INDEX,
  STEP_TOTAL,
} from './stepResolver';

// ── 공통 컴포넌트 ─────────────────────────────────────────────────────────────

function SlotRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.slotRow}>
      <Text style={styles.slotLabel}>{label}</Text>
      <Text style={styles.slotValue}>{value}</Text>
    </View>
  );
}

// ── Phase 1: 음성 안내 (슬롯 비어있음) ─────────────────────────────────────────

function VoiceGuidePhase() {
  return null;
}

// ── Phase 3: 슬롯 채우기 서브 뷰 ─────────────────────────────────────────────

function AliasInputView() {
  return null;
}

function AmountInputView({ slots }: { slots: Record<string, unknown> }) {
  return (
    <View style={styles.slotBox}>
      <SlotRow label="수취인" value={String(slots.recipient)} />
    </View>
  );
}

function CycleInputView({ slots }: { slots: Record<string, unknown> }) {
  return (
    <View style={styles.slotBox}>
      <SlotRow label="수취인" value={String(slots.recipient)} />
      <SlotRow label="금액" value={formatAmount(slots.amount)} />
    </View>
  );
}

function DayInputView({ slots }: { slots: Record<string, unknown> }) {
  const isMonthly = slots.cycle === 'monthly' || slots.cycle === '매월' || slots.cycle === '매달';
  return (
    <View style={styles.slotBox}>
      <SlotRow label="수취인" value={String(slots.recipient)} />
      <SlotRow label="금액" value={formatAmount(slots.amount)} />
      <SlotRow label="주기" value={isMonthly ? '매월' : '매주'} />
    </View>
  );
}

function ConfirmView({ slots }: { slots: Record<string, unknown> }) {
  const scheduleText = formatSchedule(slots);
  return (
    <View style={styles.slotBox}>
      <SlotRow label="수취인" value={String(slots.recipient)} />
      <SlotRow label="금액" value={formatAmount(slots.amount)} />
      <SlotRow label="일정" value={scheduleText} />
    </View>
  );
}

function AsvPendingView({ slots }: { slots: Record<string, unknown> }) {
  return (
    <>
      <View style={styles.slotBox}>
        <SlotRow label="수취인" value={String(slots.recipient ?? '')} />
        <SlotRow label="금액" value={formatAmount(slots.amount)} />
        <SlotRow label="일정" value={formatSchedule(slots)} />
      </View>
      <View style={styles.asvBadge}>
        <Text style={styles.asvBadgeText}>음성 인증 대기 중</Text>
      </View>
    </>
  );
}

// ── Phase: 자동이체 해지 ──────────────────────────────────────────────────────

function CancelRecipientInputView() {
  return null;
}

function CancelConfirmView({ slots }: { slots: Record<string, unknown> }) {
  return (
    <View style={styles.slotBox}>
      <SlotRow label="해지 대상" value={String(slots.recipient)} />
    </View>
  );
}

// ── 메인 화면 ─────────────────────────────────────────────────────────────────

export default function AutoTransferScreen() {
  const lastResponse = useVoiceResponseStore((s) => s.lastResponse);

  useEffect(() => {
    const pending = useVoiceResponseStore.getState().lastResponse?.pending_action;
    if (!pending) {
      apiClient.post('/api/voice/reset-state').catch(() => undefined);
    }
  }, []);

  const slots = lastResponse?.collected_slots ?? {};
  const awaitingAsv = lastResponse?.awaiting_asv_audio ?? false;
  const pendingAction = lastResponse?.pending_action ?? null;
  const hasSlots = Object.keys(slots).length > 0;

  const isCancel = pendingAction === 'cancel_auto_transfer';

  // 현재 페이즈 결정
  type Phase = 'voice-guide' | 'slot-filling';
  const phase: Phase = !hasSlots && !awaitingAsv ? 'voice-guide' : 'slot-filling';

  const step =
    phase === 'slot-filling' ? resolveAutoTransferStep(slots, awaitingAsv, pendingAction) : null;

  const stepTotal = isCancel ? CANCEL_STEP_TOTAL : STEP_TOTAL;
  const title = isCancel ? '자동이체 해지' : '자동이체 설정';

  return (
    <SafeAreaView style={styles.root}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
      >
        <AppScreenHeader />

        <View style={styles.titleRow}>
          <Text style={styles.title}>{title}</Text>
          {step !== null && <StepIndicator total={stepTotal} current={STEP_INDEX[step]} />}
        </View>

        {phase === 'voice-guide' && <VoiceGuidePhase />}

        {phase === 'slot-filling' && step === 'asv-pending' && <AsvPendingView slots={slots} />}
        {phase === 'slot-filling' && step === 'input-alias' && <AliasInputView />}
        {phase === 'slot-filling' && step === 'input-amount' && <AmountInputView slots={slots} />}
        {phase === 'slot-filling' && step === 'input-cycle' && <CycleInputView slots={slots} />}
        {phase === 'slot-filling' && step === 'input-day' && <DayInputView slots={slots} />}
        {phase === 'slot-filling' && step === 'confirm' && <ConfirmView slots={slots} />}
        {phase === 'slot-filling' && step === 'cancel-input-recipient' && (
          <CancelRecipientInputView />
        )}
        {phase === 'slot-filling' && step === 'cancel-confirm' && (
          <CancelConfirmView slots={slots} />
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

// ── 스타일 ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.background },
  scroll: { flex: 1 },
  content: { paddingHorizontal: LAYOUT.paddingMedium, paddingBottom: 32 },
  titleRow: { marginVertical: 16, gap: 10 },
  title: { fontSize: FONT_SIZES.button, fontWeight: '700', color: COLORS.textMain },

  slotBox: {
    backgroundColor: COLORS.surface,
    borderRadius: LAYOUT.borderRadius,
    borderWidth: 0.5,
    borderColor: COLORS.border,
    paddingHorizontal: 16,
    paddingVertical: 12,
    marginBottom: 16,
    gap: 10,
  },
  slotRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  slotLabel: { fontSize: FONT_SIZES.caption, color: COLORS.grayLight },
  slotValue: { fontSize: FONT_SIZES.body, color: COLORS.textMain, fontWeight: '600' },

  asvBadge: {
    alignSelf: 'center',
    marginTop: 8,
    backgroundColor: COLORS.yellowBg,
    borderWidth: 0.5,
    borderColor: COLORS.yellowBorder,
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  asvBadgeText: { fontSize: FONT_SIZES.caption, color: COLORS.highlightYellow, fontWeight: '600' },
});
