import { useCallback, useEffect, useRef, useState } from 'react';
import { SafeAreaView, ScrollView, StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { TopBar } from '@/components/layout';
import { COLORS, LAYOUT } from '@/constants/theme';
import { useTransferStore } from '@/store/transferStore';
import { useVoiceResponseStore } from '@/store/voiceResponseStore';
import { saveMemo } from '@/services/transferService';
import { extractApiErrorMessage } from '@/utils/errorHandler';
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
  const [memoErrorMessage, setMemoErrorMessage] = useState('');

  const phase = resolveCompletePhase(localPhase);

  const recipient = txReceipt?.toName ?? '';
  const amount = txReceipt?.amount ?? 0;
  const txId = txReceipt?.txId ?? '';
  const bankName = txReceipt?.toBankName ?? '';

  const goHome = useCallback(() => {
    resetVoiceSessionOnHome();
    router.replace('/home');
  }, []);

  const hasNavigatedRef = useRef(false);

  useEffect(() => {
    if (!txId && !hasNavigatedRef.current) {
      goHome();
    }
  }, [txId, goHome]);

  useEffect(() => {
    if (lastResponse?.navigate_to === 'home' && !hasNavigatedRef.current) {
      goHome();
    }
  }, [lastResponse?.navigate_to, goHome]);

  useEffect(() => {
    if (localPhase !== 'memo_done') return;
    const t = setTimeout(goHome, 2500);
    return () => clearTimeout(t);
  }, [localPhase, goHome]);

  const handleMemoSave = async (category: string) => {
    if (!txId) {
      goHome();
      return;
    }
    try {
      await saveMemo(txId, category);
      setMemoSaved(category);
      setLocalPhase('memo_done');
    } catch (err) {
      setMemoErrorMessage(extractApiErrorMessage(err));
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
          {phase === 'error' && (
            <CompleteErrorView errorMessage={memoErrorMessage} onGoHome={goHome} />
          )}
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
