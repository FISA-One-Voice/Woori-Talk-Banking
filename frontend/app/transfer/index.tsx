import { useEffect, useMemo, useState } from 'react';
import { SafeAreaView, ScrollView, StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { TopBar, StepIndicator } from '@/components/layout';
import { COLORS, LAYOUT } from '@/constants/theme';
import { useTransferStore } from '@/store/transferStore';
import { TRANSFER_FAILED_HOME_SUFFIX } from '@/constants/voicePrompts';
import { resetVoiceSessionOnHome } from '@/utils/resetVoiceSession';
import { useVoiceResponseStore } from '@/store/voiceResponseStore';
import { fetchRecentRecipients, executeTransfer } from '@/services/transferService';
import axios from 'axios';
import { getTtsMessage } from '@/utils/errorHandler';
import type { RecipientItem } from '@/components/display';
import {
  resolveTransferStep,
  STEP_INDEX,
  STEP_TOTAL,
  type TransferStep,
} from './stepResolver';
import { AliasStepView } from './views/AliasStepView';
import { AmountStepView } from './views/AmountStepView';
import { ConfirmStepView } from './views/ConfirmStepView';
import { AsvStepView } from './views/AsvStepView';

function recipientFromSlots(slots: Record<string, unknown>): RecipientItem | null {
  const name = (slots.recipient as string) ?? '';
  if (!name) return null;
  const bankName =
    (slots.bank_name as string) ?? (slots.bankName as string) ?? '';
  const recipientId =
    (slots.recipient_id as string) ?? (slots.recipientId as string) ?? null;
  const accountMasked =
    typeof slots.account_number === 'string'
      ? slots.account_number.replace(/\d(?=\d{4})/g, '*')
      : '';
  return {
    recipientId,
    toName: name,
    toBankName: bankName,
    accountMasked,
  };
}

export default function TransferScreen() {
  const lastResponse = useVoiceResponseStore((s) => s.lastResponse);
  const {
    setSelectedRecipient,
    setAmount,
    setTxReceipt,
    setTransferFailure,
    reset,
    selectedRecipient,
    amount,
  } = useTransferStore();

  const slots = lastResponse?.collected_slots ?? {};
  const awaitingAsv = lastResponse?.awaiting_asv_audio ?? false;
  const awaitingConfirmation = lastResponse?.awaiting_confirmation ?? false;

  const voiceStep = useMemo(
    () => resolveTransferStep(slots, awaitingAsv, awaitingConfirmation, lastResponse?.pending_action),
    [lastResponse, slots, awaitingAsv, awaitingConfirmation],
  );

  const [touchStep, setTouchStep] = useState<TransferStep | null>(null);
  const [recentList, setRecentList] = useState<RecipientItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setTouchStep(null);
  }, [lastResponse]);

  useEffect(() => {
    fetchRecentRecipients()
      .then((list) => setRecentList(list))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    const fromSlots = recipientFromSlots(slots);
    if (fromSlots) {
      setSelectedRecipient(fromSlots);
    } else {
      setSelectedRecipient(null);
    }
    if (slots.amount != null) {
      setAmount(Number(slots.amount));
    } else {
      setAmount(null);
    }
  }, [lastResponse, slots.recipient, slots.amount, setSelectedRecipient, setAmount]);

  const step = touchStep ?? voiceStep;

  const displayRecipient =
    selectedRecipient ?? recipientFromSlots(slots);
  const displayAmount =
    amount ?? (slots.amount != null ? Number(slots.amount) : null);

  const handleSelectRecipient = (item: RecipientItem) => {
    setSelectedRecipient(item);
    setTouchStep('input-amount');
  };

  const handleSelectAmount = (amt: number) => {
    setAmount(amt);
    setTouchStep('confirm');
  };

  const handleConfirm = () => {
    setTouchStep('asv-pending');
  };

  const handleAsvSkip = async () => {
    if (!displayRecipient || displayAmount == null) return;
    setLoading(true);
    try {
      const receipt = await executeTransfer(displayRecipient, displayAmount);
      setTransferFailure(null);
      setTxReceipt(receipt);
      router.replace('/transfer/complete');
    } catch (err) {
      setTxReceipt(null);
      let code: string | undefined;
      let message = getTtsMessage();
      if (axios.isAxiosError(err) && err.response?.data) {
        const body = err.response.data as { code?: string; message?: string };
        code = body.code;
        message = body.message ?? getTtsMessage(code);
        if (__DEV__) {
          console.error('[transfer] executeTransfer failed', code, message);
        }
      } else if (__DEV__) {
        console.error('[transfer] executeTransfer failed', err);
      }
      useVoiceResponseStore.getState().clearLastResponse();
      setTransferFailure({
        code,
        message: `${message}${TRANSFER_FAILED_HOME_SUFFIX}`,
      });
      router.replace('/transfer/failed');
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    if (step === 'input-amount') setTouchStep('input-alias');
    else if (step === 'confirm') setTouchStep('input-amount');
    else if (step === 'asv-pending') setTouchStep('confirm');
    else {
      reset();
      resetVoiceSessionOnHome();
      router.replace('/home');
    }
  };

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.body}>
        <TopBar variant="back" title="송금" onBack={handleBack} />
        <StepIndicator total={STEP_TOTAL} current={STEP_INDEX[step]} />
        <ScrollView contentContainerStyle={styles.content}>
          {step === 'input-alias' && (
            <AliasStepView recentList={recentList} onSelect={handleSelectRecipient} />
          )}
          {step === 'input-amount' && displayRecipient && (
            <AmountStepView
              recipientName={displayRecipient.toName}
              onSelectAmount={handleSelectAmount}
            />
          )}
          {step === 'confirm' && displayRecipient && displayAmount != null && (
            <ConfirmStepView
              recipientName={displayRecipient.toName}
              bankName={displayRecipient.toBankName}
              amount={displayAmount}
              onCancel={() => setTouchStep('input-amount')}
              onConfirm={handleConfirm}
            />
          )}
          {step === 'asv-pending' && (
            <AsvStepView loading={loading} onDevSkip={handleAsvSkip} />
          )}
        </ScrollView>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.background },
  body: { flex: 1, paddingHorizontal: LAYOUT.paddingMedium },
  content: { paddingBottom: 40, gap: 12 },
});
