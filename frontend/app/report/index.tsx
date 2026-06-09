import { getCategoryTheme } from '@/constants/categoryTheme';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import {
  ANALYTICS_PERIODS,
  AnalyticsPeriod,
  CategorySpending,
  fetchMonthlyAnalytics,
  MonthlyAnalytics,
} from '@/services/reportService';
import { CompareResult, fetchExpenseCompare } from '@/services/assetService';
import { useVoiceResponseStore } from '@/store/voiceResponseStore';
import { extractApiErrorMessage } from '@/utils/errorHandler';
import { useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { SafeAreaView, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';

type ActiveTab = 'analysis' | 'compare';
const COMPARE_PERIODS = ['이번달', '지난달', '이번주', '지난주'] as const;
const COMPARE_CATEGORIES = ['전체', '식비', '교통', '쇼핑', '의료비', '문화생활', '생활비', '기타'] as const;

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
        <Text style={styles.categoryIcon}>{theme.icon}</Text>
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
  const [activeTab, setActiveTab] = useState<ActiveTab>('analysis');

  // 지출 분석 탭 상태
  const [period, setPeriod] = useState<AnalyticsPeriod>('이번달');
  const [analytics, setAnalytics] = useState<MonthlyAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // 기간 비교 탭 상태
  const [cPeriod, setCPeriod] = useState('이번달');
  const [cComparePeriod, setCComparePeriod] = useState('지난달');
  const [cCategory, setCCategory] = useState('전체');
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareError, setCompareError] = useState<string | null>(null);

  // 음성 명령으로 compare 진입 시 자동 탭 전환 + 자동 조회
  useEffect(() => {
    const slots = useVoiceResponseStore.getState().lastResponse?.collected_slots as Record<string, string> | undefined;
    if (slots?.action === 'compare') {
      if (slots.period) setCPeriod(slots.period);
      if (slots.compare_period) setCComparePeriod(slots.compare_period);
      if (slots.category) setCCategory(slots.category);
      setActiveTab('compare');
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    setErrorMsg(null);
    fetchMonthlyAnalytics(period)
      .then(setAnalytics)
      .catch((err: unknown) => setErrorMsg(extractApiErrorMessage(err)))
      .finally(() => setLoading(false));
  }, [period]);

  const loadCompare = (p = cPeriod, cp = cComparePeriod, cat = cCategory) => {
    setCompareLoading(true);
    setCompareError(null);
    fetchExpenseCompare(p, cp, cat === '전체' ? undefined : cat)
      .then(setCompareResult)
      .catch((err: unknown) => setCompareError(extractApiErrorMessage(err)))
      .finally(() => setCompareLoading(false));
  };

  // 음성 compare 진입 시 자동 조회 트리거
  useEffect(() => {
    if (activeTab === 'compare') {
      const slots = useVoiceResponseStore.getState().lastResponse?.collected_slots as Record<string, string> | undefined;
      if (slots?.action === 'compare') loadCompare(cPeriod, cComparePeriod, cCategory);
    }
  }, [activeTab]);

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
      <ScrollView contentContainerStyle={styles.scroll}>
        {/* 헤더 */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
            <Text style={styles.backIcon}>←</Text>
          </TouchableOpacity>
          <Text style={styles.headerTitle}>지출 분석</Text>
          <View style={styles.headerRight} />
        </View>

        {/* 탭 선택 */}
        <View style={styles.tabRow}>
          <TouchableOpacity
            style={[styles.tabBtn, activeTab === 'analysis' && styles.tabBtnActive]}
            onPress={() => setActiveTab('analysis')}
          >
            <Text style={[styles.tabBtnText, activeTab === 'analysis' && styles.tabBtnTextActive]}>
              지출 분석
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.tabBtn, activeTab === 'compare' && styles.tabBtnActive]}
            onPress={() => setActiveTab('compare')}
          >
            <Text style={[styles.tabBtnText, activeTab === 'compare' && styles.tabBtnTextActive]}>
              기간 비교
            </Text>
          </TouchableOpacity>
        </View>

        {/* ── 기간 비교 탭 ── */}
        {activeTab === 'compare' && (
          <>
            <View style={styles.compareSelectors}>
              <View style={styles.compareSide}>
                <Text style={styles.compareSideLabel}>기준 기간</Text>
                {COMPARE_PERIODS.map((p) => (
                  <TouchableOpacity
                    key={p}
                    style={[styles.periodBtn, cPeriod === p && styles.periodBtnActive]}
                    onPress={() => setCPeriod(p)}
                  >
                    <Text style={[styles.periodBtnText, cPeriod === p && styles.periodBtnTextActive]}>
                      {p}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
              <Text style={styles.vsText}>vs</Text>
              <View style={styles.compareSide}>
                <Text style={styles.compareSideLabel}>비교 기간</Text>
                {COMPARE_PERIODS.map((p) => (
                  <TouchableOpacity
                    key={p}
                    style={[styles.periodBtn, cComparePeriod === p && styles.periodBtnActive]}
                    onPress={() => setCComparePeriod(p)}
                  >
                    <Text style={[styles.periodBtnText, cComparePeriod === p && styles.periodBtnTextActive]}>
                      {p}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            {/* 카테고리 필터 */}
            <View style={styles.categoryFilter}>
              <Text style={styles.compareSideLabel}>카테고리</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                <View style={styles.categoryFilterRow}>
                  {COMPARE_CATEGORIES.map((cat) => (
                    <TouchableOpacity
                      key={cat}
                      style={[styles.categoryChip, cCategory === cat && styles.categoryChipActive]}
                      onPress={() => setCCategory(cat)}
                    >
                      <Text style={[styles.categoryChipText, cCategory === cat && styles.categoryChipTextActive]}>
                        {cat}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </ScrollView>
            </View>

            <TouchableOpacity style={styles.compareBtn} onPress={() => loadCompare()}>
              <Text style={styles.compareBtnText}>비교하기</Text>
            </TouchableOpacity>

            {compareLoading && (
              <Text style={styles.compareMsg}>불러오는 중...</Text>
            )}
            {compareError && (
              <Text style={[styles.compareMsg, { color: COLORS.error }]}>{compareError}</Text>
            )}
            {!compareLoading && compareResult && (
              <View style={styles.compareCard}>
                <View style={styles.compareRow}>
                  <View style={styles.compareCell}>
                    <Text style={styles.comparePeriodLabel}>{compareResult.period}</Text>
                    <Text style={styles.compareAmount}>
                      {formatAmount(compareResult.period_amount)}
                    </Text>
                  </View>
                  <View style={styles.compareDivider} />
                  <View style={styles.compareCell}>
                    <Text style={styles.comparePeriodLabel}>{compareResult.compare_period}</Text>
                    <Text style={styles.compareAmount}>
                      {formatAmount(compareResult.compare_amount)}
                    </Text>
                  </View>
                </View>
                <View style={styles.diffRow}>
                  <Text style={styles.diffLabel}>차이</Text>
                  <Text style={[
                    styles.diffAmount,
                    { color: compareResult.diff > 0 ? COLORS.error : COLORS.success },
                  ]}>
                    {compareResult.diff > 0 ? '+' : ''}{formatAmount(compareResult.diff)}
                  </Text>
                </View>
              </View>
            )}
          </>
        )}

        {/* ── 지출 분석 탭 ── */}
        {activeTab === 'analysis' && (
          <>
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
          </>
        )}

      </ScrollView>
    </SafeAreaView>
  );
}

// ── 스타일 ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.background },
  scroll: { padding: LAYOUT.paddingMedium, gap: 12 },

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
  categoryIcon: { fontSize: 18 },
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

  tabRow: { flexDirection: 'row', gap: 8 },
  tabBtn: {
    flex: 1, paddingVertical: 12, alignItems: 'center',
    borderRadius: LAYOUT.borderRadius,
    backgroundColor: COLORS.surfaceLight,
    borderWidth: 1, borderColor: COLORS.border,
  },
  tabBtnActive: { backgroundColor: COLORS.yellowBg, borderColor: COLORS.highlightYellow },
  tabBtnText: { fontSize: FONT_SIZES.caption, color: COLORS.grayLight, fontWeight: 'bold' },
  tabBtnTextActive: { color: COLORS.highlightYellow },

  compareSelectors: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
  compareSide: { flex: 1, gap: 6 },
  compareSideLabel: { fontSize: FONT_SIZES.caption, color: COLORS.grayLight, marginBottom: 2 },
  vsText: { fontSize: FONT_SIZES.button, color: COLORS.textMain, marginTop: 28, fontWeight: 'bold' },

  compareBtn: {
    backgroundColor: COLORS.highlightYellow,
    borderRadius: LAYOUT.borderRadius,
    paddingVertical: 14,
    alignItems: 'center',
  },
  compareBtnText: { fontSize: FONT_SIZES.body, color: COLORS.background, fontWeight: 'bold' },
  compareMsg: { fontSize: FONT_SIZES.body, color: COLORS.grayLight, textAlign: 'center', marginTop: 8 },

  compareCard: {
    backgroundColor: COLORS.surface,
    borderRadius: LAYOUT.cardRadius,
    padding: 24, gap: 16,
    borderWidth: 1, borderColor: COLORS.border,
  },
  compareRow: { flexDirection: 'row', alignItems: 'center' },
  compareCell: { flex: 1, alignItems: 'center', gap: 6 },
  comparePeriodLabel: { fontSize: FONT_SIZES.caption, color: COLORS.grayLight },
  compareAmount: { fontSize: FONT_SIZES.button, color: COLORS.textMain, fontWeight: 'bold' },
  compareDivider: { width: 1, height: 40, backgroundColor: COLORS.border, marginHorizontal: 8 },
  diffRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  diffLabel: { fontSize: FONT_SIZES.body, color: COLORS.grayLight },
  diffAmount: { fontSize: FONT_SIZES.body, fontWeight: 'bold' },

  categoryFilter: { gap: 6 },
  categoryFilterRow: { flexDirection: 'row', gap: 6 },
  categoryChip: {
    paddingHorizontal: 12, paddingVertical: 6,
    borderRadius: 20,
    backgroundColor: COLORS.surfaceLight,
    borderWidth: 1, borderColor: COLORS.border,
  },
  categoryChipActive: { backgroundColor: COLORS.yellowBg, borderColor: COLORS.highlightYellow },
  categoryChipText: { fontSize: FONT_SIZES.caption, color: COLORS.grayLight },
  categoryChipTextActive: { color: COLORS.highlightYellow, fontWeight: 'bold' },
});
