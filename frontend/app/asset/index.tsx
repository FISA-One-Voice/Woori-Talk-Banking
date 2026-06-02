import { useState, useEffect } from 'react';
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
import { useRouter } from 'expo-router';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import { getTtsMessage } from '@/utils/errorHandler';
import { fetchAssetSummary, AccountItem } from '@/services/assetService';
import { useMic } from '@/context/MicContext';
import { HomeVoiceSection } from '@/components/input';
import { playTts, stopCurrentTts } from '@/utils/ttsPlayer';

function formatAmount(amount: number): string {
  if (amount >= 100000000) {
    const eok = Math.floor(amount / 100000000);
    const man = Math.floor((amount % 100000000) / 10000);
    return man > 0 ? `${eok}억 ${man.toLocaleString()}만원` : `${eok}억원`;
  }
  if (amount >= 10000) return `${Math.floor(amount / 10000).toLocaleString()}만원`;
  return `${amount.toLocaleString()}원`;
}

function AccountCard({ account }: { account: AccountItem }) {
  return (
    <View style={styles.accountCard}>
      <View style={styles.accountInfo}>
        <Text style={styles.accountBank}>{account.bank_name}</Text>
        <Text style={styles.accountAlias}>{account.alias ?? account.account_type}</Text>
      </View>
      <Text style={styles.accountBalance}>{account.balance.toLocaleString()}원</Text>
    </View>
  );
}

export default function AssetScreen() {
  const router = useRouter();
  const { voiceState, activateMic, stopMic } = useMic();
  const [accounts, setAccounts] = useState<AccountItem[]>([]);
  const [totalAsset, setTotalAsset] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAssetSummary()
      .then(({ accounts, total_asset }) => {
        setAccounts(accounts);
        setTotalAsset(total_asset);
        // 화면 진입 시 TTS 안내
        playWelcomeTts(total_asset, accounts);
      })
      .catch((err: Error) => Alert.alert('안내', getTtsMessage(err.message)))
      .finally(() => setLoading(false));
  }, []);

  async function playWelcomeTts(total: number, accountList: AccountItem[]) {
    const accountText = accountList
      .map((a) => `${a.alias ?? a.account_type} ${formatAmount(a.balance)}`)
      .join(', ');
    const text =
      `내 자산 조회 화면입니다. 총 자산은 ${formatAmount(total)}입니다. ` +
      `계좌별로는 ${accountText}입니다. ` +
      `화면 어느 곳이든 꾹 누르시면 음성 안내를 통해 지출 수입이나 거래내역을 확인하실 수 있습니다.`;
    await playTts(text);
  }

  return (
    <Pressable
      style={{ flex: 1 }}
      onLongPress={activateMic}
      onPressOut={stopMic}
      delayLongPress={600}
    >
    <SafeAreaView style={styles.root}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => { stopCurrentTts(); router.back(); }} style={styles.backBtn}>
            <Text style={styles.backIcon}>←</Text>
          </TouchableOpacity>
          <Text style={styles.headerTitle}>내 자산</Text>
          <View style={styles.headerRight} />
        </View>
        <View style={styles.ttsBubble}>
          <Text style={styles.ttsLabel}>음성 안내</Text>
          <Text style={styles.ttsText}>
            {loading ? '불러오는 중...' : `총 자산 ${formatAmount(totalAsset)} 입니다`}{'\n'}
            지출·수입 / 거래내역
          </Text>
        </View>
        <View style={styles.totalCard}>
          <Text style={styles.totalLabel}>총 자산</Text>
          <Text style={styles.totalAmount}>{totalAsset.toLocaleString()}원</Text>
        </View>

        <HomeVoiceSection
          micState={voiceState}
          primaryHint={voiceState === 'idle' ? '말씀해 주세요' : undefined}
          subCaption={voiceState === 'idle' ? '화면 어디든 꾹 눌러서 음성 명령' : undefined}
          onMicPress={activateMic}
          onMicRelease={stopMic}
        />

        {accounts.map((account) => (
          <AccountCard key={account.account_id} account={account} />
        ))}
      </ScrollView>
    </SafeAreaView>
    </Pressable>
  );
}

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
  totalLabel: { fontSize: FONT_SIZES.caption, color: COLORS.grayLight },
  totalAmount: {
    fontSize: FONT_SIZES.title,
    color: COLORS.textMain,
    fontWeight: 'bold',
  },
  voiceHint: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
    marginTop: 8,
    textAlign: 'center',
  },
  voiceIndicator: {
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 16,
    marginBottom: 8,
    padding: 24,
    borderRadius: LAYOUT.borderRadius,
    borderWidth: 1.5,
    borderColor: COLORS.border,
    backgroundColor: COLORS.surface,
    gap: 8,
  },
  voiceIndicatorListening: {
    borderColor: '#ff4444',
    backgroundColor: '#1a0000',
  },
  voiceIndicatorProcessing: {
    borderColor: COLORS.grayMedium,
    backgroundColor: COLORS.surfaceLight,
  },
  voiceIndicatorIcon: {
    fontSize: 40,
  },
  voiceIndicatorText: {
    fontSize: FONT_SIZES.body,
    color: COLORS.textMain,
    fontWeight: '600',
    textAlign: 'center',
  },
  voiceIndicatorSub: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
    textAlign: 'center',
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
  accountBank: { fontSize: FONT_SIZES.body, color: COLORS.textMain, fontWeight: 'bold' },
  accountAlias: { fontSize: FONT_SIZES.caption, color: COLORS.grayLight },
  accountBalance: { fontSize: FONT_SIZES.body, color: COLORS.textMain, fontWeight: 'bold' },
  bottomBtns: { flexDirection: 'row', gap: 12, marginTop: 8 },
  actionBtn: {
    flex: 1,
    backgroundColor: COLORS.surfaceLight,
    borderRadius: LAYOUT.borderRadius,
    paddingVertical: 16,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  actionBtnText: { fontSize: FONT_SIZES.body, color: COLORS.textMain, fontWeight: 'bold' },
});
