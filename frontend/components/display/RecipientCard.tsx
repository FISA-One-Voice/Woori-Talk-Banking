import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';

export interface RecipientItem {
  recipientId?: string | null;
  toBankName: string;
  toName: string;
  accountMasked: string;
}

interface RecipientCardProps {
  item: RecipientItem;
  onPress: (item: RecipientItem) => void;
}

export default function RecipientCard({ item, onPress }: RecipientCardProps) {
  const initial = item.toName.charAt(0);

  return (
    <TouchableOpacity style={styles.card} onPress={() => onPress(item)} activeOpacity={0.7}>
      <View style={styles.badge}>
        <Text style={styles.badgeText}>{initial}</Text>
      </View>
      <View style={styles.info}>
        <Text style={styles.name}>{item.toName}</Text>
        <Text style={styles.sub}>
          {item.toBankName} {item.accountMasked}
        </Text>
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: COLORS.surface,
    borderWidth: 0.5,
    borderColor: COLORS.border,
    borderRadius: LAYOUT.borderRadius,
    paddingVertical: 10,
    paddingHorizontal: 12,
    marginBottom: 8,
    gap: 12,
  },
  badge: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: COLORS.yellowBg,
    borderWidth: 0.5,
    borderColor: COLORS.yellowBorder,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeText: {
    fontSize: FONT_SIZES.body,
    fontWeight: '600',
    color: COLORS.highlightYellow,
  },
  info: {
    flex: 1,
  },
  name: {
    fontSize: FONT_SIZES.body,
    fontWeight: '500',
    color: COLORS.textMain,
    marginBottom: 2,
  },
  sub: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
  },
});
