import { StatusBadge } from '@/components/feedback';
import { RecipientList } from '@/components/display';
import type { RecipientItem } from '@/components/display';
import { StyleSheet, View } from 'react-native';
interface AliasStepViewProps {
  recentList: RecipientItem[];
  onSelect: (item: RecipientItem) => void;
}

export function AliasStepView({ recentList, onSelect }: AliasStepViewProps) {
  return (
    <View style={styles.wrap}>
      <StatusBadge text="수취인 선택" />
      <RecipientList items={recentList} onSelect={onSelect} />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 12 },
});
