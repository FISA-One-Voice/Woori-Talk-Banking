import { useEffect, useState } from 'react';
import { SafeAreaView, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { router } from 'expo-router';
import { TopBar } from '@/components/layout';
import { ResultScreen, SessionTimer } from '@/components/feedback';
import { SummaryBox, ActionButton } from '@/components/display';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import { useTransferStore } from '@/store/transferStore';
import { saveMemo } from '@/services/transferService';
import { getTtsMessage } from '@/utils/errorHandler';

type Step = 'summary' | 'memo_done' | 'error';

const MEMO_CATEGORIES = ['식비', '교통비', '쇼핑', '의료비', '문화생활', '기타'];

/** 메모 제안 TTS는 에이전트가 재생. 화면은 터치 보조만 제공. */
const MEMO_HINT =
  '음성으로 카테고리를 말씀하시거나, 아래 버튼을 눌러 선택할 수 있습니다.';

export default function TransferCompleteScreen() {
  const { txReceipt, reset } = useTransferStore();
  const [step, setStep] = useState<Step>('summary');
  const [memoSaved, setMemoSaved] = useState<string | null>(null);

  const recipient = txReceipt?.toName ?? '';
  const amount = txReceipt?.amount ?? 0;
  const txId = txReceipt?.txId ?? '';
  const bankName = txReceipt?.toBankName ?? '';

  useEffect(() => {
    if (!txId && !recipient) {
      router.replace('/home');
    }
  }, [txId, recipient]);

  const handleMemoSkip = () => {
    reset();
    router.replace('/home');
  };

  const handleMemoSave = async (category: string) => {
    if (!txId) {
      handleMemoSkip();
      return;
    }
    try {
      await saveMemo(txId, category);
      setMemoSaved(category);
      setStep('memo_done');
    } catch {
      setStep('error');
    }
  };

  const summaryRows = [
    { label: '받는 분', value: recipient },
    { label: '은행', value: bankName },
    { label: '금액', value: `${amount.toLocaleString()}원`, variant: 'yellow' as const },
  ].filter((r) => r.value);

  if (step === 'error') {
    return (
      <SafeAreaView style={styles.root}>
        <View style={styles.body}>
          <TopBar variant="back" title="송금" onBack={() => router.back()} />
          <ResultScreen type="error" label="송금 실패" />
          <Text style={styles.hint}>{getTtsMessage('INTERNAL_ERROR')}</Text>
          <ActionButton
            label="홈으로 돌아가기"
            variant="outline"
            onPress={() => {
              reset();
              router.replace('/home');
            }}
          />
        </View>
      </SafeAreaView>
    );
  }

  if (step === 'memo_done') {
    return (
      <SafeAreaView style={styles.root}>
        <View style={styles.body}>
          <TopBar variant="back" title="송금" onBack={() => router.back()} />
          <ResultScreen type="success" label="메모 저장 완료" />
          <SummaryBox rows={[{ label: '카테고리', value: memoSaved ?? '' }]} />
          <ActionButton label="홈으로 돌아가기" variant="outline" onPress={handleMemoSkip} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.body}>
        <TopBar variant="back" title="송금" onBack={() => router.back()} />
        <ScrollView contentContainerStyle={styles.scrollContent}>
          <ResultScreen type="success" label="송금 완료" />
          <SummaryBox rows={summaryRows} />
          <Text style={styles.hint} accessibilityRole="text">
            {MEMO_HINT}
          </Text>
          <View style={styles.categoryGrid}>
            {MEMO_CATEGORIES.map((cat) => (
              <TouchableOpacity
                key={cat}
                style={styles.categoryBtn}
                onPress={() => handleMemoSave(cat)}
                accessibilityRole="button"
                accessibilityLabel={`${cat} 카테고리로 메모 저장`}
              >
                <Text style={styles.categoryText}>{cat}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <SessionTimer onExpire={handleMemoSkip} />
          <ActionButton label="건너뛰기" variant="outline" onPress={handleMemoSkip} />
        </ScrollView>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.background },
  body: { flex: 1, paddingHorizontal: LAYOUT.paddingMedium },
  scrollContent: { paddingBottom: 24, gap: 12 },
  hint: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
    lineHeight: 24,
  },
  categoryGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginVertical: 8,
  },
  categoryBtn: {
    width: '47%',
    paddingVertical: 18,
    backgroundColor: COLORS.surfaceLight,
    borderRadius: LAYOUT.borderRadius,
    borderWidth: 1,
    borderColor: COLORS.border,
    alignItems: 'center',
  },
  categoryText: {
    fontSize: FONT_SIZES.body,
    color: COLORS.textMain,
    fontWeight: '600',
  },
});
