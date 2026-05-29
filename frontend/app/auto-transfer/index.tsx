import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { AppScreenHeader, StepIndicator } from '@/components/layout';
import { TtsBubble } from '@/components/feedback';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import { useAuthStore } from '@/store/authStore';
import { useVoiceResponseStore } from '@/store/voiceResponseStore';
import { apiClient } from '@/utils/api';
import { useAutoTransferFlowStore } from './store';
import {
  resolveAutoTransferStep,
  formatAmount,
  formatSchedule,
  STEP_INDEX,
  STEP_TOTAL,
} from './stepResolver';

// ── 타입 ──────────────────────────────────────────────────────────────────────

interface AccountItem {
  accountId: string;
  bankName: string;
  accountMasked: string;
  balance: number;
  alias: string;
  isPrimary: boolean;
}

interface AutoTransferItem {
  orderId: string;
  toName: string | null;
  bankName: string;
  accountMasked: string;
  amount: number;
  cycle: string;
  scheduledDay: number | null;
  scheduledDow: number | null;
  status: string;
  transferNote: string | null;
}

// ── 공통 컴포넌트 ─────────────────────────────────────────────────────────────

function SlotRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.slotRow}>
      <Text style={styles.slotLabel}>{label}</Text>
      <Text style={styles.slotValue}>{value}</Text>
    </View>
  );
}

// ── Phase 0: 개발자 로그인 ────────────────────────────────────────────────────

const TEST_USERS = [
  { name: '안유민', phone: '010-1111-0001' },
  { name: '김지연', phone: '010-1111-0002' },
  { name: '민채영', phone: '010-1111-0003' },
  { name: '이남길', phone: '010-1111-0004' },
  { name: '권민석', phone: '010-1111-0005' },
  { name: '이도원', phone: '010-1111-0006' },
];

function DevLoginPhase() {
  const setTokens = useAuthStore((s) => s.setTokens);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const login = async (phone: string) => {
    setLoading(true);
    setError('');
    try {
      const res = await apiClient.post('/api/users/login', { phone, pin: '000001' });
      const d = res.data?.data;
      if (d?.accessToken) {
        setTokens(d.accessToken, d.refreshToken);
      }
    } catch (e: any) {
      const msg = e?.response?.data?.message || e?.message || String(e);
      setError(`로그인 실패: ${msg}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <TtsBubble message="개발자 테스트 로그인입니다. 사용자를 선택하세요. PIN은 000001로 통일되어 있습니다." />
      <Text style={styles.sectionTitle}>테스트 계정 (PIN: 000001)</Text>
      {TEST_USERS.map((u) => (
        <Pressable
          key={u.phone}
          style={styles.card}
          onPress={() => login(u.phone)}
          disabled={loading}
        >
          <Text style={styles.cardBank}>{u.name}</Text>
          <Text style={styles.cardAlias}>{u.phone}</Text>
        </Pressable>
      ))}
      {loading && (
        <View style={styles.center}>
          <ActivityIndicator color={COLORS.highlightYellow} />
        </View>
      )}
      {!!error && <Text style={styles.errorText}>{error}</Text>}
    </>
  );
}

// ── Phase 1: 계좌 선택 ────────────────────────────────────────────────────────

function AccountSelectPhase() {
  const [accounts, setAccounts] = useState<AccountItem[]>([]);
  const [orders, setOrders] = useState<AutoTransferItem[]>([]);
  const [loading, setLoading] = useState(true);
  const setFromAccountId = useAutoTransferFlowStore((s) => s.setFromAccountId);

  useEffect(() => {
    Promise.all([
      apiClient.get('/api/auto-transfer/accounts'),
      apiClient.get('/api/auto-transfer'),
    ])
      .then(([accRes, orderRes]) => {
        setAccounts(accRes.data?.data ?? []);
        setOrders(orderRes.data?.data ?? []);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={COLORS.highlightYellow} size="large" />
      </View>
    );
  }

  return (
    <>
      <TtsBubble message="출금 계좌를 선택하세요." />

      <Text style={styles.sectionTitle}>내 계좌</Text>
      {accounts.map((a) => (
        <Pressable
          key={a.accountId}
          style={[styles.card, a.isPrimary && styles.cardPrimary]}
          onPress={() => setFromAccountId(a.accountId)}
        >
          <View style={styles.cardRow}>
            <Text style={styles.cardBank}>{a.bankName}</Text>
            {a.isPrimary && <Text style={styles.primaryBadge}>주계좌</Text>}
          </View>
          <Text style={styles.cardAlias}>{a.alias}</Text>
          <View style={styles.cardRow}>
            <Text style={styles.cardAccount}>{a.accountMasked}</Text>
            <Text style={styles.cardBalance}>{a.balance.toLocaleString('ko-KR')}원</Text>
          </View>
        </Pressable>
      ))}

      {orders.length > 0 && (
        <>
          <Text style={[styles.sectionTitle, { marginTop: 24 }]}>등록된 자동이체</Text>
          {orders.map((o) => (
            <View key={o.orderId} style={styles.orderCard}>
              <View style={styles.cardRow}>
                <Text style={styles.cardBank}>{o.toName ?? '-'}</Text>
                <Text
                  style={[
                    styles.statusBadge,
                    o.status === 'active' ? styles.statusActive : styles.statusPaused,
                  ]}
                >
                  {o.status === 'active' ? '활성' : o.status === 'paused' ? '일시정지' : '해지'}
                </Text>
              </View>
              <Text style={styles.cardAccount}>{o.bankName} {o.accountMasked}</Text>
              <Text style={styles.orderDetail}>
                {o.cycle === 'monthly'
                  ? `매월 ${o.scheduledDay}일`
                  : `매주 ${['월','화','수','목','금','토','일'][o.scheduledDow ?? 0]}요일`}
                {' · '}{o.amount.toLocaleString('ko-KR')}원
                {o.transferNote ? ` · ${o.transferNote}` : ''}
              </Text>
            </View>
          ))}
        </>
      )}
    </>
  );
}

// ── Phase 2: 음성 안내 (계좌 선택 완료, 슬롯 비어있음) ─────────────────────────

function VoiceGuidePhase() {
  return (
    <>
      <TtsBubble message="수신인 이름과 주기, 날짜, 금액을 말씀해 주세요." />
      <View style={styles.hint}>
        <Text style={styles.hintText}>화면 아무 곳이나 길게 눌러 말씀해 주세요</Text>
      </View>
    </>
  );
}

// ── Phase 3: 슬롯 채우기 서브 뷰 ─────────────────────────────────────────────

function AliasInputView() {
  return <TtsBubble message="누구에게 자동이체를 설정할까요? 이름이나 별명을 말씀해 주세요." />;
}

function AmountInputView({ slots }: { slots: Record<string, unknown> }) {
  return (
    <>
      <View style={styles.slotBox}>
        <SlotRow label="수취인" value={String(slots.alias)} />
      </View>
      <TtsBubble message="매번 얼마씩 이체할까요?" />
    </>
  );
}

function CycleInputView({ slots }: { slots: Record<string, unknown> }) {
  return (
    <>
      <View style={styles.slotBox}>
        <SlotRow label="수취인" value={String(slots.alias)} />
        <SlotRow label="금액" value={formatAmount(slots.amount)} />
      </View>
      <TtsBubble message="매월 특정 날짜에 보낼까요, 아니면 매주 특정 요일에 보낼까요?" />
    </>
  );
}

function DayInputView({ slots }: { slots: Record<string, unknown> }) {
  const isMonthly = slots.cycle === 'monthly';
  return (
    <>
      <View style={styles.slotBox}>
        <SlotRow label="수취인" value={String(slots.alias)} />
        <SlotRow label="금액" value={formatAmount(slots.amount)} />
        <SlotRow label="주기" value={isMonthly ? '매월' : '매주'} />
      </View>
      <TtsBubble
        message={
          isMonthly
            ? '매월 며칠에 이체할까요? 일부터 삼십일 중 말씀해 주세요.'
            : '매주 무슨 요일에 이체할까요?'
        }
      />
    </>
  );
}

function ConfirmView({
  slots,
  awaitingConfirmation,
}: {
  slots: Record<string, unknown>;
  awaitingConfirmation: boolean;
}) {
  const scheduleText = formatSchedule(slots);
  return (
    <>
      <View style={styles.slotBox}>
        <SlotRow label="수취인" value={String(slots.alias)} />
        <SlotRow label="금액" value={formatAmount(slots.amount)} />
        <SlotRow label="일정" value={scheduleText} />
      </View>
      <TtsBubble
        message={
          awaitingConfirmation
            ? '네 또는 아니요로 말씀해 주세요.'
            : `${slots.alias}님께 ${scheduleText}에 ${formatAmount(slots.amount)} 자동이체할까요?`
        }
        variant={awaitingConfirmation ? 'warning' : 'default'}
      />
    </>
  );
}

function AsvPendingView({ slots }: { slots: Record<string, unknown> }) {
  return (
    <>
      <View style={styles.slotBox}>
        <SlotRow label="수취인" value={String(slots.alias ?? '')} />
        <SlotRow label="금액" value={formatAmount(slots.amount)} />
        <SlotRow label="일정" value={formatSchedule(slots)} />
      </View>
      <TtsBubble message="본인 확인을 위해 다시 한 번 말씀해 주세요." variant="warning" />
      <View style={styles.asvBadge}>
        <Text style={styles.asvBadgeText}>음성 인증 대기 중</Text>
      </View>
    </>
  );
}

// ── 메인 화면 ─────────────────────────────────────────────────────────────────

export default function AutoTransferScreen() {
  const token = useAuthStore((s) => s.token);
  const { fromAccountId } = useAutoTransferFlowStore();
  const lastResponse = useVoiceResponseStore((s) => s.lastResponse);

  const slots = lastResponse?.collected_slots ?? {};
  const awaitingAsv = lastResponse?.awaiting_asv_audio ?? false;
  const awaitingConfirmation = lastResponse?.awaiting_confirmation ?? false;
  const hasSlots = Object.keys(slots).length > 0;

  // 현재 페이즈 결정
  type Phase = 'login' | 'select-account' | 'voice-guide' | 'slot-filling';
  const phase: Phase = !token
    ? 'login'
    : !fromAccountId
    ? 'select-account'
    : !hasSlots && !awaitingAsv
    ? 'voice-guide'
    : 'slot-filling';

  const step = phase === 'slot-filling' ? resolveAutoTransferStep(slots, awaitingAsv) : null;

  return (
    <SafeAreaView style={styles.root}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
      >
        <AppScreenHeader />

        <View style={styles.titleRow}>
          <Text style={styles.title}>자동이체 설정</Text>
          {step !== null && (
            <StepIndicator total={STEP_TOTAL} current={STEP_INDEX[step]} />
          )}
        </View>

        {phase === 'login'          && <DevLoginPhase />}
        {phase === 'select-account' && <AccountSelectPhase />}
        {phase === 'voice-guide'    && <VoiceGuidePhase />}

        {phase === 'slot-filling' && step === 'asv-pending'  && <AsvPendingView slots={slots} />}
        {phase === 'slot-filling' && step === 'input-alias'  && <AliasInputView />}
        {phase === 'slot-filling' && step === 'input-amount' && <AmountInputView slots={slots} />}
        {phase === 'slot-filling' && step === 'input-cycle'  && <CycleInputView slots={slots} />}
        {phase === 'slot-filling' && step === 'input-day'    && <DayInputView slots={slots} />}
        {phase === 'slot-filling' && step === 'confirm'      && (
          <ConfirmView slots={slots} awaitingConfirmation={awaitingConfirmation} />
        )}

        {phase === 'slot-filling' && (
          <View style={styles.hint}>
            <Text style={styles.hintText}>화면 아무 곳이나 길게 눌러 말씀해 주세요</Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

// ── 스타일 ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  root:    { flex: 1, backgroundColor: COLORS.background },
  scroll:  { flex: 1 },
  content: { paddingHorizontal: LAYOUT.paddingMedium, paddingBottom: 32 },
  center:  { alignItems: 'center', paddingVertical: 24 },

  titleRow: { marginVertical: 16, gap: 10 },
  title:    { fontSize: FONT_SIZES.button, fontWeight: '700', color: COLORS.textMain },

  sectionTitle: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayLight,
    fontWeight: '600',
    marginBottom: 8,
    marginTop: 4,
  },

  card: {
    backgroundColor: COLORS.surface,
    borderRadius: LAYOUT.borderRadius,
    borderWidth: 0.5,
    borderColor: COLORS.border,
    padding: 16,
    marginBottom: 10,
    gap: 6,
  },
  cardPrimary: { borderColor: COLORS.highlightYellow, borderWidth: 1 },
  cardRow:    { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  cardBank:   { fontSize: FONT_SIZES.body, color: COLORS.textMain, fontWeight: '700' },
  cardAlias:  { fontSize: FONT_SIZES.caption, color: COLORS.grayLight },
  cardAccount:{ fontSize: FONT_SIZES.caption, color: COLORS.grayMedium },
  cardBalance:{ fontSize: FONT_SIZES.body, color: COLORS.highlightYellow, fontWeight: '600' },
  primaryBadge: {
    fontSize: 18,
    color: COLORS.highlightYellow,
    backgroundColor: COLORS.yellowBg,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
  },

  orderCard: {
    backgroundColor: COLORS.surface,
    borderRadius: LAYOUT.borderRadius,
    borderWidth: 0.5,
    borderColor: COLORS.border,
    padding: 14,
    marginBottom: 8,
    gap: 4,
  },
  orderDetail: { fontSize: FONT_SIZES.caption, color: COLORS.grayMedium },
  statusBadge: {
    fontSize: 18,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
    overflow: 'hidden',
  },
  statusActive: { color: COLORS.success, backgroundColor: '#0d2d0d' },
  statusPaused: { color: COLORS.warning, backgroundColor: '#2d1d00' },

  slotBox: {
    backgroundColor: COLORS.surface,
    borderRadius: LAYOUT.borderRadius,
    borderWidth: 0.5,
    borderColor: COLORS.border,
    paddingHorizontal: 16,
    paddingVertical: 12,
    marginBottom: 16,
    gap: 10,
  },
  slotRow:   { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  slotLabel: { fontSize: FONT_SIZES.caption, color: COLORS.grayLight },
  slotValue: { fontSize: FONT_SIZES.body, color: COLORS.textMain, fontWeight: '600' },

  asvBadge: {
    alignSelf: 'center',
    marginTop: 8,
    backgroundColor: COLORS.yellowBg,
    borderWidth: 0.5,
    borderColor: COLORS.yellowBorder,
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  asvBadgeText: { fontSize: FONT_SIZES.caption, color: COLORS.highlightYellow, fontWeight: '600' },

  hint:     { marginTop: 32, alignItems: 'center' },
  hintText: { fontSize: FONT_SIZES.caption, color: COLORS.grayDark, textAlign: 'center' },

  errorText: { fontSize: FONT_SIZES.caption, color: COLORS.error, textAlign: 'center', marginTop: 8 },
});
