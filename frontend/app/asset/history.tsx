import { useState, useEffect, useRef } from 'react';
import {
  Alert,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { useMic } from '@/context/MicContext';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import { getTtsMessage } from '@/utils/errorHandler';
import { fetchExpenseSummary, fetchTransactionHistory, CategoryItem, TransactionItem } from '@/services/assetService';
import { playTts, stopCurrentTts } from '@/utils/ttsPlayer';

type Step = 'slot' | 'result' | 'history' | 'error';

function periodToDays(period: string): number {
  if (period === '이번달') return 30;
  if (period === '지난달') return 60;
  if (period === '최근 7일') return 7;
  return 30;
}


export default function HistoryScreen() {
  const router = useRouter();
  const { type } = useLocalSearchParams<{ type: string }>();
  const { activateMic, stopMic } = useMic();

  const [step, setStep] = useState<Step>(type === 'history' ? 'history' : 'slot');
  const [period, setPeriod] = useState('이번달');
  const [transactions, setTransactions] = useState<TransactionItem[]>([]);
  const [topCategories, setTopCategories] = useState<CategoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [categoriesLoading, setCategoriesLoading] = useState(false);
  const announcedRef = useRef(false);

  const income = transactions.filter((t) => t.category === '수입').reduce((s, t) => s + t.amount, 0);
  const expense = transactions.filter((t) => t.category !== '수입').reduce((s, t) => s + t.amount, 0);

  const fetchHistory = async (days: number) => {
    setLoading(true);
    fetchTransactionHistory(days)
      .then(setTransactions)
      .catch((err: Error) => {
        Alert.alert('안내', getTtsMessage(err.message));
        setTransactions([]);
      })
      .finally(() => setLoading(false));
  };

  // 화면 진입 시 TTS 안내
  useEffect(() => {
    if (step === 'slot') {
      playTts('지출 수입 화면입니다. 이번달, 지난달, 최근 7일 중 기간을 선택해 주세요.');
    }
    if (step === 'history') {
      fetchHistory(30);
    }
  }, [step]);

  // result 단계: 거래내역 + 카테고리 둘 다 로드 완료 후 TTS 안내
  useEffect(() => {
    if (step !== 'result' || loading || categoriesLoading || announcedRef.current) return;
    if (transactions.length === 0) return;
    announcedRef.current = true;

    const catText = topCategories
      .slice(0, 3)
      .map((c) => `${c.category} ${c.amount.toLocaleString()}원`)
      .join(', ');
    const text =
      `${period} 수입은 ${income.toLocaleString()}원, 지출은 ${expense.toLocaleString()}원입니다.` +
      (catText ? ` 주요 지출은 ${catText}입니다.` : '');
    playTts(text);
  }, [step, loading, categoriesLoading, transactions, topCategories]);

  // history 단계: 거래내역 로드 완료 후 TTS로 전체 읽기
  useEffect(() => {
    if (step !== 'history' || loading || transactions.length === 0) return;
    const txText = transactions
      .slice(0, 10)
      .map((tx) => {
        const date = new Date(tx.created_at).toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' });
        const sign = tx.amount > 0 ? '입금' : '출금';
        return `${date} ${tx.to_name ?? ''} ${sign} ${Math.abs(tx.amount).toLocaleString()}원`;
      })
      .join('. ');
    const intro = `최근 거래내역 ${transactions.length}건입니다. `;
    playTts(intro + txText);
  }, [step, loading, transactions]);

  if (step === 'slot') {
    return (
      <Pressable style={{flex:1}} onLongPress={activateMic} onPressOut={stopMic} delayLongPress={600}>
      <SafeAreaView style={styles.root}>
        <View style={styles.container}>
          <View style={styles.header}>
            <TouchableOpacity onPress={() => { stopCurrentTts(); router.back(); }} style={styles.backBtn}>
              <Text style={styles.backIcon}>←</Text>
            </TouchableOpacity>
            <Text style={styles.screenTitle}>지출·수입</Text>
            <View style={styles.headerRight} />
          </View>

          <View style={styles.ttsBubble}>
            <Text style={styles.ttsLabel}>슬롯 미완성</Text>
            <Text style={styles.ttsTextYellow}>
              어느 기간을{'\n'}알려드릴까요?
            </Text>
          </View>

          <TouchableOpacity style={styles.listenBtn}>
            <Text style={styles.listenBtnText}>● 듣고 있어요</Text>
          </TouchableOpacity>

          <View style={styles.periodBox}>
            <Text style={styles.periodLabel}>기간</Text>
            <Text style={styles.periodHint}>기간을 말씀해 주세요</Text>
          </View>

          <Text style={styles.periodExample}>예: 이번달, 지난달, 최근 1주일</Text>

          {['이번달', '지난달', '최근 7일'].map((p) => (
            <TouchableOpacity
              key={p}
              style={[styles.periodBtn, period === p && styles.periodBtnActive]}
              onPress={() => {
                stopCurrentTts();
                setPeriod(p);
                announcedRef.current = false;
                fetchHistory(periodToDays(p));
                setCategoriesLoading(true);
                fetchExpenseSummary(periodToDays(p))
                  .then((s) => setTopCategories(s.top_categories))
                  .catch(() => setTopCategories([]))
                  .finally(() => setCategoriesLoading(false));
                setStep('result');
              }}
            >
              <Text style={[styles.periodBtnText, period === p && styles.periodBtnTextActive]}>
                {p}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </SafeAreaView>
      </Pressable>
    );
  }

  if (step === 'result') {
    return (
      <Pressable style={{flex:1}} onLongPress={activateMic} onPressOut={stopMic} delayLongPress={600}>
      <SafeAreaView style={styles.root}>
        <View style={styles.container}>
          <View style={styles.header}>
            <TouchableOpacity onPress={() => setStep('slot')} style={styles.backBtn}>
              <Text style={styles.backIcon}>←</Text>
            </TouchableOpacity>
            <Text style={styles.screenTitle}>지출·수입</Text>
            <View style={styles.headerRight} />
          </View>

          <View style={styles.ttsBubble}>
            <Text style={styles.ttsLabel}>음성 안내</Text>
            <Text style={styles.ttsText}>
              {period}{'\n'}
              수입 {(income / 10000).toFixed(0)}만 / 지출 {Math.abs(expense / 10000).toFixed(0)}만
            </Text>
          </View>

          <View style={styles.resultCard}>
            <View style={styles.resultRow}>
              <Text style={styles.resultLabel}>기간</Text>
              <Text style={styles.resultLabel}>{period}</Text>
            </View>
            <View style={styles.resultRow}>
              <Text style={styles.resultLabel}>수입</Text>
              <Text style={[styles.resultAmount, { color: COLORS.success }]}>
                +{income.toLocaleString()}원
              </Text>
            </View>
            <View style={styles.resultRow}>
              <Text style={styles.resultLabel}>지출</Text>
              <Text style={[styles.resultAmount, { color: COLORS.error }]}>
                {expense.toLocaleString()}원
              </Text>
            </View>
          </View>

          {topCategories.length > 0 && (
            <View style={styles.categoryCard}>
              <Text style={styles.categoryTitle}>카테고리별 지출 Top 5</Text>
              {topCategories.map((item) => (
                <View key={item.category} style={styles.categoryRow}>
                  <Text style={styles.categoryName}>{item.category}</Text>
                  <Text style={styles.categoryAmount}>{item.amount.toLocaleString()}원</Text>
                </View>
              ))}
            </View>
          )}
        </View>
      </SafeAreaView>
      </Pressable>
    );
  }

  if (step === 'history') {
    return (
      <Pressable style={{flex:1}} onLongPress={activateMic} onPressOut={stopMic} delayLongPress={600}>
      <SafeAreaView style={styles.root}>
        <ScrollView contentContainerStyle={styles.scroll}>
          <View style={styles.header}>
            <TouchableOpacity onPress={() => { stopCurrentTts(); router.back(); }} style={styles.backBtn}>
              <Text style={styles.backIcon}>←</Text>
            </TouchableOpacity>
            <Text style={styles.screenTitle}>거래내역</Text>
            <View style={styles.headerRight} />
          </View>

          <View style={styles.ttsBubble}>
            <Text style={styles.ttsLabel}>음성 안내</Text>
            <Text style={styles.ttsText}>최근 거래내역</Text>
          </View>

          {loading ? (
            <Text style={{ color: COLORS.grayLight, textAlign: 'center', marginTop: 20 }}>불러오는 중...</Text>
          ) : transactions.length === 0 ? (
            <Text style={{ color: COLORS.grayLight, textAlign: 'center', marginTop: 20 }}>거래내역이 없습니다</Text>
          ) : (
            transactions.map((tx) => (
              <View key={tx.tx_id} style={styles.txCard}>
                <View style={styles.txLeft}>
                  <Text style={styles.txDate}>
                    {new Date(tx.created_at).toLocaleDateString('ko-KR', { month: '2-digit', day: '2-digit' })}
                  </Text>
                  <Text style={styles.txName}>{tx.to_name}</Text>
                  {tx.memo ? (
                    <Text style={styles.txMemo}>📝 {tx.memo}</Text>
                  ) : null}
                </View>
                <Text style={[
                  styles.txAmount,
                  { color: tx.amount > 0 ? COLORS.success : COLORS.error }
                ]}>
                  {tx.amount > 0 ? '+' : ''}{tx.amount.toLocaleString()}원
                </Text>
              </View>
            ))
          )}
        </ScrollView>
      </SafeAreaView>
      </Pressable>
    );
  }

  return (
    <SafeAreaView style={styles.root}>
      <View style={[styles.container, styles.errorContainer]}>
        <Text style={styles.errorTitle}>잘 듣지 못했습니다</Text>
        <Text style={styles.errorSub}>홈으로 돌아갑니다</Text>
        <View style={styles.errorIcon}>
          <Text style={{ fontSize: 40, color: COLORS.error }}>✕</Text>
        </View>
        <Text style={[styles.ttsText, { color: COLORS.error }]}>2회 연속 실패</Text>
        <TouchableOpacity
          style={styles.homeBtn}
          onPress={() => router.replace('/home')}
        >
          <Text style={styles.homeBtnText}>홈으로</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.background },
  container: {
    flex: 1,
    padding: LAYOUT.paddingMedium,
    paddingTop: 40,
    gap: 12,
  },
  scroll: {
    padding: LAYOUT.paddingMedium,
    paddingTop: 40,
    gap: 12,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  backBtn: { width: 40 },
  backIcon: { fontSize: FONT_SIZES.button, color: COLORS.textMain },
  headerRight: { width: 40 },
  screenTitle: {
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
  ttsLabel: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.highlightYellow,
    marginBottom: 6,
  },
  ttsText: {
    fontSize: FONT_SIZES.body,
    color: COLORS.textMain,
    lineHeight: 36,
  },
  ttsTextYellow: {
    fontSize: FONT_SIZES.body,
    color: COLORS.highlightYellow,
    lineHeight: 36,
    fontWeight: 'bold',
  },
  listenBtn: {
    backgroundColor: 'transparent',
    borderWidth: 1.5,
    borderColor: COLORS.highlightYellow,
    borderRadius: 999,
    paddingVertical: 10,
    paddingHorizontal: 28,
    alignSelf: 'center',
  },
  listenBtnText: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.highlightYellow,
    fontWeight: 'bold',
  },
  periodBox: {
    backgroundColor: COLORS.surface,
    borderRadius: LAYOUT.borderRadius,
    padding: 16,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  periodLabel: { fontSize: FONT_SIZES.body, color: COLORS.textMain },
  periodHint: { fontSize: FONT_SIZES.caption, color: COLORS.grayLight, marginTop: 4 },
  periodExample: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
    marginTop: -4,
  },
  periodBtn: {
    backgroundColor: COLORS.surfaceLight,
    borderRadius: LAYOUT.borderRadius,
    paddingVertical: 14,
    paddingHorizontal: 20,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  periodBtnActive: { borderColor: COLORS.highlightYellow, backgroundColor: COLORS.yellowBg },
  periodBtnText: { fontSize: FONT_SIZES.body, color: COLORS.grayLight },
  periodBtnTextActive: { color: COLORS.highlightYellow },
  resultCard: {
    backgroundColor: COLORS.surface,
    borderRadius: LAYOUT.cardRadius,
    padding: 24,
    gap: 16,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  resultRow: { flexDirection: 'row', justifyContent: 'space-between' },
  resultLabel: { fontSize: FONT_SIZES.body, color: COLORS.textMain },
  resultAmount: { fontSize: FONT_SIZES.body, fontWeight: 'bold' },
  txCard: {
    backgroundColor: COLORS.surface,
    borderRadius: LAYOUT.borderRadius,
    padding: 16,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  txLeft: { gap: 4, flex: 1 },
  txDate: { fontSize: FONT_SIZES.caption, color: COLORS.grayLight },
  txName: { fontSize: FONT_SIZES.body, color: COLORS.textMain },
  txMemo: { fontSize: FONT_SIZES.caption, color: COLORS.grayMedium },
  txAmount: { fontSize: FONT_SIZES.body, fontWeight: 'bold' },
  errorContainer: { justifyContent: 'center', alignItems: 'center' },
  errorTitle: { fontSize: FONT_SIZES.button, color: COLORS.textMain, fontWeight: 'bold' },
  errorSub: { fontSize: FONT_SIZES.body, color: COLORS.grayLight },
  errorIcon: {
    width: 80,
    height: 80,
    borderRadius: 40,
    borderWidth: 3,
    borderColor: COLORS.error,
    justifyContent: 'center',
    alignItems: 'center',
    marginVertical: 16,
  },
  homeBtn: {
    marginTop: 20,
    backgroundColor: COLORS.surfaceLight,
    borderRadius: LAYOUT.borderRadius,
    paddingVertical: 14,
    paddingHorizontal: 40,
  },
  homeBtnText: { fontSize: FONT_SIZES.body, color: COLORS.textMain },
  categoryCard: {
    backgroundColor: COLORS.surface,
    borderRadius: LAYOUT.cardRadius,
    padding: 20,
    gap: 12,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  categoryTitle: {
    fontSize: FONT_SIZES.body,
    color: COLORS.textMain,
    fontWeight: 'bold',
  },
  categoryRow: { flexDirection: 'row', justifyContent: 'space-between' },
  categoryName: { fontSize: FONT_SIZES.body, color: COLORS.textMain },
  categoryAmount: { fontSize: FONT_SIZES.body, color: COLORS.error, fontWeight: 'bold' },
});
