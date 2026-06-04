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
import { useRouter } from 'expo-router';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import { getTtsMessage } from '@/utils/errorHandler';
import { fetchAssetSummary, AccountItem } from '@/services/assetService';
import { speakText, stopAllTts } from '@/utils/ttsManager';

function formatAmount(amount: number): string {
  if (amount >= 100000000) {
    const eok = Math.floor(amount / 100000000);
    const man = Math.floor((amount % 100000000) / 10000);
    return man > 0 ? `${eok}억 ${man.toLocaleString()}만원` : `${eok}억원`;
  }
  if (amount >= 10000) return `${Math.floor(amount / 10000).toLocaleString()}만원`;
  return `${amount.toLocaleString()}원`;
}

function AccountCard({ account, onPress }: { account: AccountItem; onPress?: () => void }) {
  return (
    <TouchableOpacity style={styles.accountCard} onPress={onPress} activeOpacity={0.8}>
      <View style={styles.accountInfo}>
        <Text style={styles.accountBank}>{account.bank_name}</Text>
        <Text style={styles.accountAlias}>{account.alias ?? account.account_type}</Text>
      </View>
      <Text style={styles.accountBalance}>{account.balance.toLocaleString()}원</Text>
    </TouchableOpacity>
  );
}

export default function AssetScreen() {
  const router = useRouter();
  const [accounts, setAccounts] = useState<AccountItem[]>([]);
  const [totalAsset, setTotalAsset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [announceText, setAnnounceText] = useState('');

  useEffect(() => {
    fetchAssetSummary()
      .then(({ accounts, total_asset }) => {
        setAccounts(accounts);
        setTotalAsset(total_asset);
        const accountText = accounts
          .map((a) => `${a.bank_name} ${a.alias ?? a.account_type} ${formatAmount(a.balance)}`)
          .join(', ');
        const text =
          `내 자산 조회 화면입니다. 총 자산은 ${formatAmount(total_asset)}입니다. ` +
          `계좌별로는 ${accountText}입니다. ` +
          `화면 아래의 지출·수입이나 거래내역 버튼을 눌러 확인하실 수 있습니다. ` +
          `꾹 누르시면 음성으로 조회할 수 있습니다.`;
        setAnnounceText(text);
        const accountVoice = accounts
          .map((a) => `${a.alias ?? a.account_type} ${formatAmount(a.balance)}`)
          .join(', ');
        speakText(
          `총 자산은 ${formatAmount(total_asset)}입니다. ` +
          `${accountVoice}. ` +
          `지출 수입 내역이나 거래내역은 화면을 꾹 눌러 음성으로 말씀하시면 알 수 있습니다.`
        );
      })
      .catch((err: Error) => Alert.alert('안내', getTtsMessage(err.message)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <SafeAreaView style={styles.root}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => { stopAllTts(); router.back(); }} style={styles.backBtn}>
            <Text style={styles.backIcon}>←</Text>
          </TouchableOpacity>
          <Text style={styles.headerTitle}>내 자산</Text>
          <View style={styles.headerRight} />
        </View>

        <TouchableOpacity
          style={styles.ttsBubble}
          onPress={() => announceText && speakText(announceText)}
          activeOpacity={0.8}
        >
          <Text style={styles.ttsLabel}>음성 안내 · 탭하면 다시 듣기</Text>
          <Text style={styles.ttsText}>
            {loading ? '불러오는 중...' : `총 자산 ${formatAmount(totalAsset)} 입니다`}{'\n'}
            지출·수입 / 거래내역 버튼으로 확인하세요
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.totalCard}
          onPress={() => announceText && speakText(announceText)}
          activeOpacity={0.85}
        >
          <Text style={styles.totalLabel}>총 자산</Text>
          <Text style={styles.totalAmount}>{totalAsset.toLocaleString()}원</Text>
        </TouchableOpacity>

        {accounts.map((account) => (
          <AccountCard
            key={account.account_id}
            account={account}
            onPress={() => announceText && speakText(announceText)}
          />
        ))}

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
