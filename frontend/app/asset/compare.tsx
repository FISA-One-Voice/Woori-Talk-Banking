import { useEffect, useRef, useState } from 'react';
import {
  SafeAreaView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useRouter } from 'expo-router';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import { fetchExpenseCompare, CompareResult } from '@/services/assetService';
import { speakText, stopAllTts } from '@/utils/ttsManager';
import { useVoiceResponseStore } from '@/store/voiceResponseStore';

function normalizePeriod(period: string): string {
  if (period === '최근7일') return '최근 7일';
  return period;
}

export default function CompareScreen() {
  const router = useRouter();
  const [result, setResult] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [announceText, setAnnounceText] = useState('');
  const announcedRef = useRef(false);

  // voiceResponseStore에서 slots 읽기
  const liveLastResponse = useVoiceResponseStore((state) => state.lastResponse);
  const lastAudioRef = useRef<string | undefined>(liveLastResponse?.audio);

  const getSlotsFromStore = () => {
    const resp = useVoiceResponseStore.getState().lastResponse;
    const slots = resp?.collected_slots as Record<string, string> | undefined;
    return {
      period: slots?.period ? normalizePeriod(slots.period) : '이번달',
      comparePeriod: slots?.compare_period ? normalizePeriod(slots.compare_period) : '지난달',
      category: slots?.category ?? undefined,
    };
  };

  const loadCompare = async (period: string, comparePeriod: string, category?: string) => {
    setLoading(true);
    announcedRef.current = false;
    try {
      const data = await fetchExpenseCompare(period, comparePeriod, category);
      setResult(data);
    } catch {
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const { period, comparePeriod, category } = getSlotsFromStore();
    loadCompare(period, comparePeriod, category);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // 같은 화면에서 새 compare 음성 명령이 왔을 때 갱신
  useEffect(() => {
    if (!liveLastResponse?.audio) return;
    if (liveLastResponse.navigate_to !== 'asset/compare') return;
    if (liveLastResponse.audio === lastAudioRef.current) return;
    lastAudioRef.current = liveLastResponse.audio;

    const slots = liveLastResponse.collected_slots as Record<string, string> | undefined;
    const period = slots?.period ? normalizePeriod(slots.period) : '이번달';
    const comparePeriod = slots?.compare_period ? normalizePeriod(slots.compare_period) : '지난달';
    const category = slots?.category ?? undefined;
    loadCompare(period, comparePeriod, category);
  }, [liveLastResponse]); // eslint-disable-line react-hooks/exhaustive-deps

  // TTS 안내 텍스트 생성
  useEffect(() => {
    if (!result || loading || announcedRef.current) return;
    announcedRef.current = true;

    const subject = result.category ? `${result.category} 지출` : '지출';
    const direction = result.diff > 0 ? `${Math.abs(result.diff).toLocaleString()}원 증가` :
      result.diff < 0 ? `${Math.abs(result.diff).toLocaleString()}원 감소` : '동일';
    const text =
      `${result.period} ${subject}은 ${result.period_amount.toLocaleString()}원, ` +
      `${result.compare_period}은 ${result.compare_amount.toLocaleString()}원으로 ${direction}했습니다.`;
    setAnnounceText(text);
  }, [result, loading]);

  const diff = result?.diff ?? 0;
  const diffColor = diff > 0 ? COLORS.error : diff < 0 ? COLORS.success : COLORS.grayLight;
  const diffLabel = diff > 0 ? `▲ ${Math.abs(diff).toLocaleString()}원 증가` :
    diff < 0 ? `▼ ${Math.abs(diff).toLocaleString()}원 감소` : '변동 없음';

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.container}>
        {/* 헤더 */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => { stopAllTts(); router.back(); }} style={styles.backBtn}>
            <Text style={styles.backIcon}>←</Text>
          </TouchableOpacity>
          <Text style={styles.screenTitle}>기간 비교</Text>
          <View style={styles.headerRight} />
        </View>

        {/* TTS 버블 */}
        <TouchableOpacity
          style={styles.ttsBubble}
          onPress={() => announceText && speakText(announceText)}
          activeOpacity={0.8}
        >
          <Text style={styles.ttsLabel}>음성 안내 · 탭하면 다시 듣기</Text>
          {loading ? (
            <Text style={styles.ttsText}>불러오는 중...</Text>
          ) : result ? (
            <Text style={styles.ttsText}>
              {result.category ? `[${result.category}] ` : ''}
              {result.period} vs {result.compare_period}
            </Text>
          ) : (
            <Text style={styles.ttsText}>데이터를 불러올 수 없습니다</Text>
          )}
        </TouchableOpacity>

        {/* 비교 카드 */}
        {result && !loading && (
          <>
            <View style={styles.compareRow}>
              {/* 기준 기간 */}
              <View style={[styles.periodCard, styles.periodCardLeft]}>
                <Text style={styles.periodLabel}>{result.period}</Text>
                <Text style={styles.periodAmount}>
                  {result.period_amount.toLocaleString()}원
                </Text>
              </View>

              {/* vs 구분 */}
              <View style={styles.vsBox}>
                <Text style={styles.vsText}>vs</Text>
              </View>

              {/* 비교 기간 */}
              <View style={[styles.periodCard, styles.periodCardRight]}>
                <Text style={styles.periodLabel}>{result.compare_period}</Text>
                <Text style={styles.periodAmount}>
                  {result.compare_amount.toLocaleString()}원
                </Text>
              </View>
            </View>

            {/* 차이 표시 */}
            <View style={styles.diffCard}>
              {result.category && (
                <View style={styles.categoryBadge}>
                  <Text style={styles.categoryBadgeText}>{result.category}</Text>
                </View>
              )}
              <Text style={[styles.diffText, { color: diffColor }]}>{diffLabel}</Text>
            </View>
          </>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.background },
  container: { flex: 1, padding: LAYOUT.paddingMedium, paddingTop: 40, gap: 16 },
  header: {
    flexDirection: 'row', alignItems: 'center',
    justifyContent: 'space-between', marginBottom: 4,
  },
  backBtn: { width: 40 },
  backIcon: { fontSize: FONT_SIZES.button, color: COLORS.textMain },
  headerRight: { width: 40 },
  screenTitle: {
    fontSize: FONT_SIZES.button, color: COLORS.textMain,
    fontWeight: 'bold', textAlign: 'center', flex: 1,
  },
  ttsBubble: {
    backgroundColor: COLORS.yellowBg, borderRadius: LAYOUT.borderRadius,
    padding: 16, borderWidth: 1, borderColor: COLORS.yellowBorder,
  },
  ttsLabel: { fontSize: FONT_SIZES.caption, color: COLORS.highlightYellow, marginBottom: 6 },
  ttsText: { fontSize: FONT_SIZES.body, color: COLORS.textMain, lineHeight: 36 },
  compareRow: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
  },
  periodCard: {
    flex: 1, backgroundColor: COLORS.surface, borderRadius: LAYOUT.cardRadius,
    padding: 20, alignItems: 'center', gap: 10,
    borderWidth: 1, borderColor: COLORS.border,
  },
  periodCardLeft: { borderColor: COLORS.highlightYellow },
  periodCardRight: { borderColor: COLORS.border },
  periodLabel: { fontSize: FONT_SIZES.caption, color: COLORS.grayLight },
  periodAmount: { fontSize: FONT_SIZES.body, color: COLORS.textMain, fontWeight: 'bold' },
  vsBox: { alignItems: 'center', paddingHorizontal: 4 },
  vsText: { fontSize: FONT_SIZES.caption, color: COLORS.grayMedium },
  diffCard: {
    backgroundColor: COLORS.surface, borderRadius: LAYOUT.borderRadius,
    padding: 20, alignItems: 'center', gap: 10,
    borderWidth: 1, borderColor: COLORS.border,
  },
  diffText: { fontSize: FONT_SIZES.button, fontWeight: 'bold' },
  categoryBadge: {
    backgroundColor: COLORS.surfaceLight, borderRadius: 20,
    paddingVertical: 4, paddingHorizontal: 14,
    borderWidth: 1, borderColor: COLORS.highlightYellow,
  },
  categoryBadgeText: { fontSize: FONT_SIZES.caption, color: COLORS.highlightYellow },
});
