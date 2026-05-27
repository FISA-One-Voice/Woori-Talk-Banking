import { useState } from 'react';
import {
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useRouter } from 'expo-router';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';

const MOCK_ACCOUNTS = [
  { account_id: '1', bank_name: '우리은행', account_type: '입출금', alias: '주거래 통장', balance: 10000000, is_primary: true },
  { account_id: '2', bank_name: '우리은행', account_type: '저축', alias: '저축 통장', balance: 5000000, is_primary: false },
];
const TOTAL_ASSET = MOCK_ACCOUNTS.reduce((sum, a) => sum + a.balance, 0);

function formatAmount(amount: number): string {
  if (amount >= 100000000) {
    const eok = Math.floor(amount / 100000000);
    const man = Math.floor((amount % 100000000) / 10000);
    return man > 0 ? `${eok}억 ${man.toLocaleString()}만원` : `${eok}억원`;
  }
  if (amount >= 10000) {
    return `${Math.floor(amount / 10000).toLocaleString()}만원`;
  }
  return `${amount.toLocaleString()}원`;
}

export default function AssetScreen() {
  const router = useRouter();
  const [isListening, setIsListening] = useState(false);

  return (
    <SafeAreaView style={styles.root}>
      <ScrollView contentContainerStyle={styles.scroll}>

        {/* 헤더 */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
            <Text style={styles.backIcon}>←</Text>
          </TouchableOpacity>
          <Text style={styles.headerTitle}>내 자산</Text>
          <View style={styles.headerRight} />
        </View>

        {/* TTS 안내 버블 — 노란 배경 */}
        <View style={styles.ttsBubble}>
          <Text style={styles.ttsLabel}>음성 안내</Text>
          <Text style={styles.ttsText}>
            총 자산 {formatAmount(TOTAL_ASSET)} 입니다{'\n'}
            지출·수입 / 거래내역
          </Text>
        </View>

        {/* 총 자산 카드 */}
        <View style={styles.totalCard}>
          <Text style={styles.totalLabel}>총 자산</Text>
          <Text style={styles.totalAmount}>{TOTAL_ASSET.toLocaleString()}원</Text>
          <TouchableOpacity
            style={[styles.listenBtn, isListening && styles.listenBtnActive]}
            onPress={() => setIsListening((v) => !v)}
          >
            <Text style={[styles.listenBtnText, isListening && styles.listenBtnTextActive]}>
            {isListening ? '● 듣고 있어요' : '● 듣고 있어요'}
            </Text>
          </TouchableOpacity>
        </View>

        {/* 계좌 목록 */}
        {MOCK_ACCOUNTS.map((account) => (
          <View key={account.account_id} style={styles.accountCard}>
            <View style={styles.accountInfo}>
              <Text style={styles.accountBank}>{account.bank_name}</Text>
              <Text style={styles.accountAlias}>{account.alias ?? account.account_type}</Text>
            </View>
            <Text style={styles.accountBalance}>{account.balance.toLocaleString()}원</Text>
          </View>
        ))}

        {/* 하단 버튼 */}
        <View style={styles.bottomBtns}>
          <TouchableOpacity
            style={styles.actionBtn}
            onPress={() => router.push('/asset/history?type=expense')}
          >
            <Text style={styles.actionBtnText}>지출·수입</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.actionBtn}
            onPress={() => router.push('/asset/history?type=history')}
          >
            <Text style={styles.actionBtnText}>거래내역</Text>
          </TouchableOpacity>
        </View>

      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  scroll: {
    padding: LAYOUT.paddingMedium,
    gap: 12,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  backBtn: { width: 40 },
  backIcon: {
    fontSize: FONT_SIZES.button,
    color: COLORS.textMain,
  },
  headerRight: { width: 40 },
  headerTitle: {
    fontSize: FONT_SIZES.button,
    color: COLORS.textMain,
    fontWeight: 'bold',
    textAlign: 'center',
    flex: 1,
  },

  // TTS 버블 — 노란 배경
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

  totalCard: {
    backgroundColor: COLORS.surfaceLight,
    borderRadius: LAYOUT.cardRadius,
    padding: 24,
    alignItems: 'center',
    gap: 12,
  },
  totalLabel: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayLight,
  },
  totalAmount: {
    fontSize: FONT_SIZES.title,
    color: COLORS.textMain,
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

  accountCard: {
    backgroundColor: COLORS.surface,
    borderRadius: LAYOUT.borderRadius,
    padding: 16,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  accountInfo: { gap: 4 },
  accountBank: {
    fontSize: FONT_SIZES.body,
    color: COLORS.textMain,
    fontWeight: 'bold',
  },
  accountAlias: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayLight,
  },
  accountBalance: {
    fontSize: FONT_SIZES.body,
    color: COLORS.textMain,
    fontWeight: 'bold',
  },

  bottomBtns: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 8,
  },
  actionBtn: {
    flex: 1,
    backgroundColor: COLORS.surfaceLight,
    borderRadius: LAYOUT.borderRadius,
    paddingVertical: 16,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  actionBtnText: {
    fontSize: FONT_SIZES.body,
    color: COLORS.textMain,
    fontWeight: 'bold',
  },
});