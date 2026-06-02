import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';

export interface VoiceQuickMenuItem {
  icon: string;
  label: string;
  voiceHint: string;
  onPress: () => void;
}

interface VoiceQuickMenuGridProps {
  items: VoiceQuickMenuItem[];
}

export default function VoiceQuickMenuGrid({ items }: VoiceQuickMenuGridProps) {
  return (
    <View style={styles.grid}>
      {items.map((item, index) => (
        <TouchableOpacity
          key={`${item.label}-${index}`}
          style={styles.card}
          onPress={item.onPress}
          activeOpacity={0.7}
        >
          <Text style={styles.icon}>{item.icon}</Text>
          <Text style={styles.label}>{item.label}</Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 12,
  },
  card: {
    width: '47%',
    backgroundColor: COLORS.surface,
    borderWidth: 0.5,
    borderColor: COLORS.grayDeep,
    borderRadius: LAYOUT.borderRadius + 1,
    padding: LAYOUT.cardPadding,
    gap: 4,
  },
  icon: {
    fontSize: 24,
  },
  label: {
    fontSize: FONT_SIZES.body,
    fontWeight: '500',
    color: COLORS.textMain,
  },
  voiceHint: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
  },
});
