import { SafeAreaView, ScrollView, StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { TopBar } from '@/components/layout';
import { ActionButton } from '@/components/display';
import { COLORS, LAYOUT } from '@/constants/theme';
import { useVoiceResponseStore } from '@/store/voiceResponseStore';
import { useTransferStore } from '@/store/transferStore';

const MOCK_EMPTY_AUDIO = '';

const SCENARIOS = [
  {
    label: '① 수취인 수집 중 (recipient만)',
    data: {
      audio: MOCK_EMPTY_AUDIO,
      navigate_to: 'transfer',
      collected_slots: { recipient: '김하나' },
      awaiting_confirmation: false,
      awaiting_asv_audio: false,
      awaiting_memo_decision: false,
      transcript: '김하나한테 보내줘',
    },
  },
  {
    label: '② 금액까지 수집 → 확인 대기',
    data: {
      audio: MOCK_EMPTY_AUDIO,
      navigate_to: 'transfer',
      collected_slots: { recipient: '김하나', amount: 50000 },
      awaiting_confirmation: true,
      awaiting_asv_audio: false,
      awaiting_memo_decision: false,
      transcript: '5만원 보내줘',
    },
  },
  {
    label: '③ ASV(음성 인증) 대기',
    data: {
      audio: MOCK_EMPTY_AUDIO,
      navigate_to: 'transfer',
      collected_slots: { recipient: '김하나', amount: 50000 },
      awaiting_confirmation: false,
      awaiting_asv_audio: true,
      awaiting_memo_decision: false,
      transcript: null,
    },
  },
  {
    label: '④ 이체 완료 → complete 화면',
    data: {
      audio: MOCK_EMPTY_AUDIO,
      navigate_to: 'transfer/complete',
      collected_slots: { recipient: '김하나', amount: 50000, txId: 'test-tx-001' },
      awaiting_confirmation: false,
      awaiting_asv_audio: false,
      awaiting_memo_decision: true,
      transcript: '네',
    },
    receipt: {
      txId: 'test-tx-001',
      toName: '김하나',
      toBankName: '하나은행',
      amount: 50000,
    },
  },
];

export default function TransferTestScreen() {
  const setLastResponse = useVoiceResponseStore((s) => s.setLastResponse);
  const setTxReceipt = useTransferStore((s) => s.setTxReceipt);

  const handleScenario = (scenario: (typeof SCENARIOS)[number]) => {
    setLastResponse(scenario.data);
    if ('receipt' in scenario && scenario.receipt) {
      setTxReceipt(scenario.receipt);
    }
    const target = scenario.data.navigate_to ?? 'transfer';
    router.replace(`/${target}` as any);
  };

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.body}>
        <TopBar variant="back" title="이체 플로우 테스트" onBack={() => router.back()} />
        <ScrollView contentContainerStyle={styles.content}>
          {SCENARIOS.map((s) => (
            <ActionButton
              key={s.label}
              label={s.label}
              variant="outline"
              onPress={() => handleScenario(s)}
            />
          ))}
        </ScrollView>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.background },
  body: { flex: 1, paddingHorizontal: LAYOUT.paddingMedium },
  content: { gap: 12, paddingTop: 24, paddingBottom: 40 },
});
