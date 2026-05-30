import { useEffect, useState } from 'react';
import { SafeAreaView, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { router } from 'expo-router';
import { TopBar } from '@/components/layout';
import { TtsBubble, StatusBadge, FingerprintIcon } from '@/components/feedback';
import { SummaryBox, RecipientList, ActionButton } from '@/components/display';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import { useTransferStore } from '@/store/transferStore';
import { useVoiceResponseStore } from '@/store/voiceResponseStore';
import { fetchRecentRecipients, executeTransfer } from '@/services/transferService';
import type { RecipientItem } from '@/components/display';

type Step = 'recipient' | 'amount' | 'confirm' | 'asv';

function getInitialStep(): Step {
  const lastResponse = useVoiceResponseStore.getState().lastResponse;
  if (!lastResponse) return 'recipient';
  const { awaiting_asv_audio, collected_slots } = lastResponse;
  if (awaiting_asv_audio) return 'asv';
  if (collected_slots?.recipient && collected_slots?.amount) return 'confirm';
  if (collected_slots?.recipient) return 'amount';
  return 'recipient';
}

const AMOUNT_PRESETS = [10000, 30000, 50000, 100000, 300000, 500000];

export default function TransferScreen() {
  const { setSelectedRecipient, setAmount, setTxReceipt, reset } = useTransferStore();
  const [step, setStep] = useState<Step>(getInitialStep);
  const [recentList, setRecentList] = useState<RecipientItem[]>([]);
  const [selected, setSelected] = useState<RecipientItem | null>(() => {
    const slots = useVoiceResponseStore.getState().lastResponse?.collected_slots;
    const name = (slots?.recipient as string) ?? null;
    if (!name) return null;
    return { recipientId: null, toName: name, toBankName: '', accountMasked: '' };
  });
  const [selectedAmount, setSelectedAmount] = useState<number | null>(() => {
    const slots = useVoiceResponseStore.getState().lastResponse?.collected_slots;
    return slots?.amount ? Number(slots.amount) : null;
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchRecentRecipients()
      .then((list) => setRecentList(list))
      .catch(() => undefined);
    syncFromAgentSlots();
  }, []);

  function syncFromAgentSlots() {
    const lastResponse = useVoiceResponseStore.getState().lastResponse;
    if (!lastResponse) return;

    const { collected_slots, awaiting_asv_audio } = lastResponse;
    const slotRecipient = (collected_slots?.recipient as string) ?? null;
    const slotAmount = collected_slots?.amount ? Number(collected_slots.amount) : null;

    if (slotRecipient) {
      const item: RecipientItem = {
        recipientId: null,
        toName: slotRecipient,
        toBankName: '',
        accountMasked: '',
      };
      setSelected(item);
      setSelectedRecipient(item);
    }

    if (slotAmount) {
      setSelectedAmount(slotAmount);
      setAmount(slotAmount);
    }

    if (awaiting_asv_audio) {
      setStep('asv');
    } else if (slotRecipient && slotAmount) {
      setStep('confirm');
    } else if (slotRecipient) {
      setStep('amount');
    }
  }

  const handleSelectRecipient = (item: RecipientItem) => {
    setSelected(item);
    setSelectedRecipient(item);
    setStep('amount');
  };

  const handleSelectAmount = (amount: number) => {
    setSelectedAmount(amount);
    setAmount(amount);
    setStep('confirm');
  };

  const handleConfirm = () => {
    setStep('asv');
  };

  const handleAsvSkip = async () => {
    if (!selected || !selectedAmount) return;
    setLoading(true);
    try {
      const receipt = await executeTransfer(selected, selectedAmount);
      setTxReceipt(receipt);
      router.push('/transfer/complete');
    } catch {
      router.push('/transfer/complete');
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    if (step === 'amount') setStep('recipient');
    else if (step === 'confirm') setStep('amount');
    else if (step === 'asv') setStep('confirm');
    else { reset(); router.back(); }
  };

  const summaryRows = [
    { label: '받는 분', value: selected?.toName ?? '' },
    { label: '은행', value: selected?.toBankName ?? '' },
    { label: '금액', value: selectedAmount ? `${selectedAmount.toLocaleString()}원` : '', variant: 'yellow' as const },
  ].filter((r) => r.value);

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.body}>
        <TopBar variant="back" title="송금" onBack={handleBack} />
        <ScrollView contentContainerStyle={styles.content}>

          {step === 'recipient' && (
            <>
              <TtsBubble message="누구에게 보내시겠어요?" autoPlay />
              <StatusBadge text="수취인 선택" />
              <RecipientList items={recentList} onSelect={handleSelectRecipient} />
            </>
          )}

          {step === 'amount' && (
            <>
              <TtsBubble message={`${selected?.toName}님께 얼마를 보낼까요?`} autoPlay />
              <StatusBadge text="금액 선택" />
              <View style={styles.amountGrid}>
                {AMOUNT_PRESETS.map((amt) => (
                  <TouchableOpacity
                    key={amt}
                    style={styles.amountBtn}
                    onPress={() => handleSelectAmount(amt)}
                  >
                    <Text style={styles.amountText}>{amt.toLocaleString()}원</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </>
          )}

          {step === 'confirm' && (
            <>
              <TtsBubble
                message={`${selected?.toName}님께 ${selectedAmount?.toLocaleString()}원 이체할까요?`}
                autoPlay
              />
              <SummaryBox rows={summaryRows} />
              <View style={styles.row}>
                <ActionButton label="취소" variant="outline" flex={1} onPress={() => setStep('amount')} />
                <ActionButton label="확인" flex={2} onPress={handleConfirm} />
              </View>
            </>
          )}

          {step === 'asv' && (
            <>
              <TtsBubble message="목소리로 인증해 주세요." autoPlay />
              <FingerprintIcon />
              <StatusBadge text="음성 인증 중" />
              {__DEV__ && (
                <ActionButton
                  label="[개발] 인증 건너뛰기"
                  variant="outline"
                  onPress={handleAsvSkip}
                  disabled={loading}
                />
              )}
            </>
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
  row: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 8,
  },
});
