import { StyleSheet } from 'react-native';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';

export const showcaseStyles = StyleSheet.create({
  sectionLabel: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
    marginBottom: 8,
    marginTop: 16,
  },
  hint: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayDark,
    textAlign: 'center',
    marginTop: 4,
    marginBottom: 8,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 8,
  },
});
