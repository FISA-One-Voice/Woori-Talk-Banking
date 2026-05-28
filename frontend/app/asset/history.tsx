import { useState, useEffect } from 'react';
import {
  Alert,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import { getTtsMessage } from '@/utils/errorHandler';
import { apiClient, ApiResponse } from '@/utils/api';
import { useAuthStore } from '@/store/authStore';

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

  const [step, setStep] = useState<Step>(type === 'history' ? 'history' : 'slot');
  const [period, setPeriod] = useState('이번달');
  const [transactions, setTransactions] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const income = transactions.filter((t) => t.category === '수입').reduce((s, t) => s + t.amount, 0);
  const expense = transactions.filter((t) => t.category !== '수입').reduce((s, t) => s + t.amount, 0);

  // 거래내역 API 호출
  const fetchHistory = async (days: number) => {
    const token = useAuthStore.getState().token;
    if (!token) {
      Alert.alert('로그인 필요', '이 기능을 사용하려면 로그인해주세요.');
      router.push('/login');
      return;
    }

    setLoading(true);
    try {
      const response = await apiClient.get<ApiResponse<{ transactions: any[] }>>(
        `/api/asset/history?days=${days}`
      );
      if (response.data.success) {
        setTransactions(response.data.data?.transactions ?? []);
      } else {
        console.warn('[asset/history]', getTtsMessage(response.data.code));
        setTransactions([]);
      }
    } catch {
      console.warn('[asset/history]', getTtsMessage('NETWORK_ERROR'));
    } finally {
      setLoading(false);
    }
  };

  // 거래내역 화면 진입 시 자동 호출
  useEffect(() => {
    if (step === 'history') {
      fetchHistory(30);
    }
  }, [step]);

  // ── 슬롯 요청 화면 (SCR005-F03)
  if (step === 'slot') {
    return (
      <SafeAreaView style={styles.root}>
        <View style={styles.container}>
          <View style={styles.header}>
            <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
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
                setPeriod(p);
                fetchHistory(periodToDays(p));
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
    );
  }

  // ── 지출·수입 결과 화면 (SCR005-F04)
  if (step === 'result') {
    return (
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
        </View>
      </SafeAreaView>
    );
  }

  // ── 거래내역 목록 화면 (SCR005-F05)
  if (step === 'history') {
    return (
      <SafeAreaView style={styles.root}>
        <ScrollView contentContainerStyle={styles.scroll}>
          <View style={styles.header}>
            <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
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
    );
  }

  // ── 2회 연속 실패 화면 (SCR005-E01)
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
  txLeft: { gap: 4 },
  txDate: { fontSize: FONT_SIZES.caption, color: COLORS.grayLight },
  txName: { fontSize: FONT_SIZES.body, color: COLORS.textMain },
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
});