import { useCallback, useEffect, useState } from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useRouter } from 'expo-router';
import { TopBar } from '@/components/layout';
import { ActionButton, SummaryBox } from '@/components/display';
import { ResultScreen, StatusBadge } from '@/components/feedback';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import { useVoiceResponseStore } from '@/store/voiceResponseStore';
import { apiClient, ApiResponse } from '@/utils/api';
import { formatAmount, formatSchedule } from './stepResolver';

type CompletePhase = 'summary' | 'memo-pending' | 'memo-done';

const MEMO_CATEGORIES = ['식비', '교통비', '쇼핑', '의료비', '문화생활', '기타'];

// ── 완료 요약 뷰 ──────────────────────────────────────────────────────────────

function SummaryView({
  summaryRows,
  onGoHome,
}: {
  summaryRows: Array<{ label: string; value: string; variant?: 'yellow' }>;
  onGoHome: () => void;
}) {
  return (
    <>
      <ResultScreen type="success" label="자동이체 등록 완료" />
      <SummaryBox rows={summaryRows} />
      <ActionButton label="홈으로 돌아가기" variant="outline" onPress={onGoHome} />
    </>
  );
}

// ── 메모 대기 뷰 ──────────────────────────────────────────────────────────────

function MemoPendingView({
  onMemoSave,
  onSkip,
}: {
  onMemoSave: (category: string) => void;
  onSkip: () => void;
}) {
  return (
    <View style={styles.memoWrap}>
      <StatusBadge text="메모 대기 중" />
      <Text style={styles.memoHint}>
        음성으로 카테고리를 말씀하시거나, 아래 버튼을 눌러 선택할 수 있습니다.
      </Text>
      <View style={styles.categoryGrid}>
        {MEMO_CATEGORIES.map((cat) => (
          <TouchableOpacity
            key={cat}
            style={styles.categoryBtn}
            onPress={() => onMemoSave(cat)}
            accessibilityRole="button"
          >
            <Text style={styles.categoryText}>{cat}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <ActionButton label="건너뛰기" variant="outline" onPress={onSkip} />
    </View>
  );
}

// ── 메모 완료 뷰 ──────────────────────────────────────────────────────────────

function MemoDoneView({
  category,
  onGoHome,
}: {
  category: string;
  onGoHome: () => void;
}) {
  return (
    <>
      <ResultScreen type="success" label="메모 저장 완료" />
      <SummaryBox rows={[{ label: '카테고리', value: category }]} />
      <ActionButton label="홈으로 돌아가기" variant="outline" onPress={onGoHome} />
    </>
  );
}

// ── 메인 화면 ─────────────────────────────────────────────────────────────────

export default function AutoTransferCompleteScreen() {
  const router = useRouter();
  const lastResponse = useVoiceResponseStore((s) => s.lastResponse);
  const slots = lastResponse?.collected_slots ?? {};

  const awaitingMemo = lastResponse?.awaiting_memo_decision ?? false;
  const [localPhase, setLocalPhase] = useState<CompletePhase>(
    awaitingMemo ? 'memo-pending' : 'summary',
  );
  const [savedCategory, setSavedCategory] = useState<string | null>(null);

  // 음성 응답으로 awaiting_memo_decision 변화 감지
  useEffect(() => {
    if (awaitingMemo) {
      setLocalPhase('memo-pending');
    }
  }, [awaitingMemo]);

  // 홈 이동 (음성 navigate_to="home" 처리는 _layout이 담당, 수동 버튼용)
  const goHome = useCallback(() => {
    router.replace('/home');
  }, [router]);

  const handleMemoSave = async (category: string) => {
    const orderId = slots.orderId as string | undefined;
    if (!orderId) {
      goHome();
      return;
    }
    try {
      await apiClient.post<ApiResponse<unknown>>(
        `/api/auto-transfer/${orderId}/label`,
        { transferNote: category },
      );
      setSavedCategory(category);
      setLocalPhase('memo-done');
    } catch {
      goHome();
    }
  };

  const summaryRows = [
    { label: '수취인', value: String(slots.recipient ?? '') },
    { label: '금액', value: formatAmount(slots.amount), variant: 'yellow' as const },
    { label: '일정', value: formatSchedule(slots) },
  ].filter((r) => r.value);

  const phase = awaitingMemo ? 'memo-pending' : localPhase;

  return (
    <View style={styles.root}>
      <View style={styles.body}>
        <TopBar variant="back" title="자동이체" onBack={goHome} />
        <ScrollView contentContainerStyle={styles.content}>
          {phase === 'summary' && (
            <SummaryView summaryRows={summaryRows} onGoHome={goHome} />
          )}
          {phase === 'memo-pending' && (
            <MemoPendingView onMemoSave={handleMemoSave} onSkip={goHome} />
          )}
          {phase === 'memo-done' && (
            <MemoDoneView category={savedCategory ?? ''} onGoHome={goHome} />
          )}
        </ScrollView>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.background },
  body: { flex: 1, paddingHorizontal: LAYOUT.paddingMedium },
  content: { paddingBottom: 40, gap: 12 },
  memoWrap: { gap: 16, alignItems: 'stretch' },
  memoHint: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
    lineHeight: 24,
    textAlign: 'center',
  },
  categoryGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
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
