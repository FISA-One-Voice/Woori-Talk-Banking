import { getCategoryTheme } from '@/constants/categoryTheme';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import {
  ANALYTICS_PERIODS,
  AnalyticsPeriod,
  CategorySpending,
  fetchMonthlyAnalytics,
  MonthlyAnalytics,
} from '@/services/reportService';
import { extractApiErrorMessage } from '@/utils/errorHandler';
import { useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { Image, SafeAreaView, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';

// ── 금액 포맷 ─────────────────────────────────────────────────────────────────

function formatAmount(amount: number): string {
  if (amount >= 100_000_000) {
    const eok = Math.floor(amount / 100_000_000);
    const man = Math.floor((amount % 100_000_000) / 10_000);
    return man > 0 ? `${eok}억 ${man.toLocaleString()}만원` : `${eok}억원`;
  }
  if (amount >= 10_000) return `${Math.floor(amount / 10_000).toLocaleString()}만원`;
  return `${amount.toLocaleString()}원`;
}

// ── 서브 컴포넌트 ─────────────────────────────────────────────────────────────

function PeriodSelector({
  selected,
  onSelect,
}: {
  selected: AnalyticsPeriod;
  onSelect: (p: AnalyticsPeriod) => void;
}) {
  return (
    <View style={styles.periodRow}>
      {ANALYTICS_PERIODS.map((p) => (
        <TouchableOpacity
          key={p}
          style={[styles.periodBtn, selected === p && styles.periodBtnActive]}
          onPress={() => onSelect(p)}
          accessibilityRole="button"
          accessibilityState={{ selected: selected === p }}
        >
          <Text style={[styles.periodBtnText, selected === p && styles.periodBtnTextActive]}>
            {p}
          </Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}

function CategoryBar({ item, maxAmount }: { item: CategorySpending; maxAmount: number }) {
  const theme = getCategoryTheme(item.category);
  // 최대값 대비 상대 너비 — ratio 직접 사용 시 1위가 항상 100%가 아닐 수 있으므로 상대 계산
  const relativeWidth = maxAmount > 0 ? (item.amount / maxAmount) * 100 : 0;

  return (
    <View style={styles.categoryRow}>
      <View style={styles.categoryLabel}>
        <Image source={theme.icon} style={styles.categoryIcon} />
        <Text style={styles.categoryName}>{item.category}</Text>
      </View>
      <View style={styles.barContainer}>
        <View style={styles.barBg}>
          <View
            style={[styles.barFill, { width: `${relativeWidth}%`, backgroundColor: theme.color }]}
          />
        </View>
        <Text style={styles.categoryAmount}>{formatAmount(item.amount)}</Text>
      </View>
      <Text style={styles.categoryRatio}>{item.ratio.toFixed(1)}%</Text>
    </View>
  );
}

// ── 메인 화면 ─────────────────────────────────────────────────────────────────

export default function ReportScreen() {
  const router = useRouter();
  const [period, setPeriod] = useState<AnalyticsPeriod>('이번달');
  const [analytics, setAnalytics] = useState<MonthlyAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setErrorMsg(null);
    fetchMonthlyAnalytics(period)
      .then(setAnalytics)
      .catch((err: unknown) => setErrorMsg(extractApiErrorMessage(err)))
      .finally(() => setLoading(false));
  }, [period]);

  const ttsSummary = loading
    ? '불러오는 중입니다.'
    : errorMsg
      ? errorMsg
      : analytics
        ? `${analytics.period} 총 지출은 ${formatAmount(analytics.total_spending)}입니다. 가장 많이 쓴 카테고리는 ${analytics.top_category}입니다.`
        : '';

  const maxAmount = analytics?.categories[0]?.amount ?? 0;

  return (
    <SafeAreaView style={styles.root}>
      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
        {/* 헤더 */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
            <Text style={styles.backIcon}>←</Text>
          </TouchableOpacity>
          <Text style={styles.headerTitle}>지출 분석</Text>
          <View style={styles.headerRight} />
        </View>

        {/* TTS 버블 */}
        <View style={styles.ttsBubble}>
          <Text style={styles.ttsLabel}>음성 안내</Text>
          <Text style={styles.ttsText}>{ttsSummary}</Text>
        </View>

        {/* 기간 선택 */}
        <PeriodSelector selected={period} onSelect={setPeriod} />

        {/* 총 지출 카드 */}
        <View style={styles.totalCard}>
          <Text style={styles.totalLabel}>{period} 총 지출</Text>
          <Text style={styles.totalAmount}>
            {loading ? '—' : analytics ? formatAmount(analytics.total_spending) : '—'}
          </Text>
          {analytics && (
            <Text style={styles.topCategory}>
              최다 지출: {analytics.top_category}
            </Text>
          )}
        </View>

        {/* 카테고리 바 차트 */}
        {!loading && analytics && analytics.categories.length > 0 && (
          <View style={styles.chartCard}>
            <Text style={styles.chartTitle}>카테고리별 지출</Text>
            {analytics.categories.map((item) => (
              <CategoryBar key={item.category} item={item} maxAmount={maxAmount} />
            ))}
          </View>
        )}

        {/* 내역 없음 */}
        {!loading && !errorMsg && analytics && analytics.categories.length === 0 && (
          <View style={styles.emptyBox}>
            <Text style={styles.emptyText}>{period} 지출 내역이 없습니다.</Text>
          </View>
        )}

        {/* 에러 */}
        {!loading && errorMsg && (
          <View style={styles.emptyBox}>
            <Text style={styles.emptyText}>{errorMsg}</Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

// ── 스타일 ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.background },
  scroll: { flex: 1 },
  scrollContent: { padding: LAYOUT.paddingMedium, gap: 12, paddingBottom: 32 },

  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  backBtn: { width: 40 },
  backIcon: { fontSize: FONT_SIZES.button, color: COLORS.textMain },
  headerRight: { width: 40 },
  headerTitle: {
    fontSize: FONT_SIZES.button,
    color: COLORS.textMain,
    fontWeight: 'bold',
    textAlign: 'center',
    flex: 1,
  },

  ttsBubble: {
    backgroundColor: COLORS.yellowBg,
    borderRadius: LAYOUT.borderRadius,
    padding: 16,
    borderWidth: 1,
    borderColor: COLORS.yellowBorder,
  },
  ttsLabel: { fontSize: FONT_SIZES.caption, color: COLORS.highlightYellow, marginBottom: 6 },
  ttsText: { fontSize: FONT_SIZES.body, color: COLORS.textMain, lineHeight: 36 },

  periodRow: { flexDirection: 'row', gap: 8 },
  periodBtn: {
    flex: 1,
    paddingVertical: 12,
    alignItems: 'center',
    borderRadius: LAYOUT.borderRadius,
    backgroundColor: COLORS.surfaceLight,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  periodBtnActive: {
    backgroundColor: COLORS.yellowBg,
    borderColor: COLORS.highlightYellow,
  },
  periodBtnText: { fontSize: FONT_SIZES.caption, color: COLORS.grayLight, fontWeight: 'bold' },
  periodBtnTextActive: { color: COLORS.highlightYellow },

  totalCard: {
    backgroundColor: COLORS.surfaceLight,
    borderRadius: LAYOUT.cardRadius,
    padding: 24,
    alignItems: 'center',
    gap: 8,
  },
  totalLabel: { fontSize: FONT_SIZES.caption, color: COLORS.grayLight },
  totalAmount: { fontSize: FONT_SIZES.title, color: COLORS.textMain, fontWeight: 'bold' },
  topCategory: { fontSize: FONT_SIZES.caption, color: COLORS.highlightYellow },

  chartCard: {
    backgroundColor: COLORS.surface,
    borderRadius: LAYOUT.cardRadius,
    padding: 20,
    gap: 16,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  chartTitle: { fontSize: FONT_SIZES.body, color: COLORS.textMain, fontWeight: 'bold' },

  categoryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  categoryLabel: { flexDirection: 'row', alignItems: 'center', gap: 4, width: 80 },
  categoryIcon: { width: 18, height: 18 },
  categoryName: { fontSize: FONT_SIZES.caption, color: COLORS.textMain, flex: 1 },
  barContainer: { flex: 1, gap: 4 },
  barBg: {
    height: 12,
    backgroundColor: COLORS.grayMuted,
    borderRadius: 6,
    overflow: 'hidden',
  },
  barFill: { height: '100%', borderRadius: 6 },
  categoryAmount: { fontSize: FONT_SIZES.caption, color: COLORS.grayLight },
  categoryRatio: { fontSize: FONT_SIZES.caption, color: COLORS.grayMedium, width: 44, textAlign: 'right' },

  emptyBox: {
    backgroundColor: COLORS.surface,
    borderRadius: LAYOUT.borderRadius,
    padding: 24,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  emptyText: { fontSize: FONT_SIZES.body, color: COLORS.grayLight },
});
