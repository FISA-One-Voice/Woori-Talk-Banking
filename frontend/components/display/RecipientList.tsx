import { StyleSheet, Text, View } from 'react-native';
import { COLORS, FONT_SIZES } from '@/constants/theme';
import RecipientCard, { type RecipientItem } from './RecipientCard';

interface RecipientListProps {
  items: RecipientItem[];
  onSelect: (item: RecipientItem) => void;
}

export default function RecipientList({ items, onSelect }: RecipientListProps) {
  if (items.length === 0) return null;

  return (
    <View style={styles.wrap}>
      <Text style={styles.label}>최근 수취인</Text>
      {items.map((item, i) => (
        <RecipientCard key={item.recipientId ?? i} item={item} onPress={onSelect} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    marginBottom: 12,
  },
  label: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayDark,
    marginBottom: 8,
  },
});
