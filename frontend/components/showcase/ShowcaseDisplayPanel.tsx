import { Text, View } from 'react-native';
import {
  ActionButton,
  InfoBox,
  SummaryBox,
  QuickMenuGrid,
  VoiceQuickMenuGrid,
} from '@/components/display';
import { showcaseStyles as styles } from './showcaseStyles';

export default function ShowcaseDisplayPanel() {
  return (
    <>
      <Text style={styles.sectionLabel}>InfoBox</Text>
      <InfoBox label="수취인" value="엄마 통장" state="default" />
      <InfoBox label="금액" value="50,000원" state="ok" />
      <InfoBox label="메모" state="empty" />

      <Text style={styles.sectionLabel}>SummaryBox</Text>
      <SummaryBox
        rows={[
          { label: '보내는 분', value: '권민석' },
          { label: '받는 분', value: '엄마', variant: 'yellow' },
          { label: '금액', value: '50,000원', variant: 'ok' },
        ]}
      />

      <Text style={styles.sectionLabel}>QuickMenuGrid</Text>
      <QuickMenuGrid
        items={[
          { icon: '💰', label: '잔액조회', onPress: () => alert('잔액조회') },
          { icon: '💸', label: '이체', onPress: () => alert('이체') },
          { icon: '📋', label: '거래내역', onPress: () => alert('거래내역') },
          { icon: '🔔', label: '알림', onPress: () => alert('알림') },
        ]}
      />

      <Text style={styles.sectionLabel}>VoiceQuickMenuGrid (홈 퀵메뉴)</Text>
      <VoiceQuickMenuGrid
        items={[
          { icon: '↗', label: '이체하기', voiceHint: '"이체해줘"', onPress: () => alert('이체') },
          { icon: '📊', label: '내 자산', voiceHint: '"내 자산"', onPress: () => alert('자산') },
          { icon: '🔁', label: '자동이체', voiceHint: '"자동이체"', onPress: () => alert('자동이체') },
          { icon: '🎁', label: '이벤트', voiceHint: '"이벤트"', onPress: () => alert('이벤트') },
        ]}
      />

      <Text style={styles.sectionLabel}>ActionButton</Text>
      <View style={styles.buttonRow}>
        <ActionButton label="확인" onPress={() => alert('확인')} flex={1} />
        <ActionButton label="취소" variant="outline" onPress={() => alert('취소')} flex={1} />
      </View>
      <ActionButton label="삭제" variant="destructive" onPress={() => alert('삭제')} />
    </>
  );
}
