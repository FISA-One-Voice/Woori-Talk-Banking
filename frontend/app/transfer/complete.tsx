import { useCallback, useEffect, useState } from 'react';
import { SafeAreaView, ScrollView, StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { TopBar } from '@/components/layout';
import { COLORS, LAYOUT } from '@/constants/theme';
import { useTransferStore } from '@/store/transferStore';
import { useVoiceResponseStore } from '@/store/voiceResponseStore';
import { saveMemo } from '@/services/transferService';
import { resetVoiceSessionOnHome } from '@/utils/resetVoiceSession';
import { resolveCompletePhase, type CompletePhase } from './completeStepResolver';
import { CompleteSummaryView } from './views/CompleteSummaryView';
import { CompleteMemoDoneView } from './views/CompleteMemoDoneView';
import { CompleteErrorView } from './views/CompleteErrorView';

export default function TransferCompleteScreen() {
  const { txReceipt, reset } = useTransferStore();
  const lastResponse = useVoiceResponseStore((s) => s.lastResponse);
  const [localPhase, setLocalPhase] = useState<CompletePhase>('summary');
  const [memoSaved, setMemoSaved] = useState<string | null>(null);

  const phase = resolveCompletePhase(localPhase);

  const recipient = txReceipt?.toName ?? '';
  const amount = txReceipt?.amount ?? 0;
  const txId = txReceipt?.txId ?? '';
  const bankName = txReceipt?.toBankName ?? '';

  const goHome = useCallback(() => {
    resetVoiceSessionOnHome();
    router.replace('/home');
  }, []);

  useEffect(() => {
    if (!txId && !recipient) {
      goHome();
    }
  }, [txId, recipient, goHome]);

  useEffect(() => {
    if (lastResponse?.navigate_to === 'home') {
      resetVoiceSessionOnHome();
    }
  }, [lastResponse?.navigate_to]);

  const handleMemoSave = async (category: string) => {
    if (!txId) {
      goHome();
      return;
    }
    try {
      await saveMemo(txId, category);
      setMemoSaved(category);
      setLocalPhase('memo_done');
    } catch {
      setLocalPhase('error');
    }
  };

  const summaryRows = [
    { label: '받는 분', value: recipient },
    { label: '은행', value: bankName },
    { label: '금액', value: `${amount.toLocaleString('ko-KR')}원`, variant: 'yellow' as const },
  ].filter((r) => r.value);

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.body}>
        <TopBar variant="back" title="송금" onBack={goHome} />
        <ScrollView contentContainerStyle={styles.scrollContent}>
          {phase === 'error' && <CompleteErrorView onGoHome={goHome} />}
          {phase === 'memo_done' && (
            <CompleteMemoDoneView category={memoSaved ?? ''} onGoHome={goHome} />
          )}
          {phase === 'summary' && (
            <CompleteSummaryView
              summaryRows={summaryRows}
              onMemoSave={handleMemoSave}
              onSkip={goHome}
            />
          )}
        </ScrollView>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.background },
  body: { flex: 1, paddingHorizontal: LAYOUT.paddingMedium },
  scrollContent: { paddingBottom: 24, gap: 12 },
});
