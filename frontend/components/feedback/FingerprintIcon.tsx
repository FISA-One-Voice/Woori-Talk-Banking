import { StyleSheet, Text, View } from 'react-native';
import { COLORS, FONT_SIZES } from '@/constants/theme';

export default function FingerprintIcon() {
  return (
    <View style={styles.wrap}>
      <View style={styles.ring}>
        <Text style={styles.icon}>🫆</Text>
      </View>
      <Text style={styles.label}>생체 인식 대기</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    alignItems: 'center',
    marginVertical: 24,
  },
  ring: {
    width: 96,
    height: 96,
    borderRadius: 48,
    borderWidth: 2,
    borderColor: COLORS.highlightYellow,
    backgroundColor: COLORS.yellowBg,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  icon: {
    fontSize: 48,
  },
  label: {
    fontSize: FONT_SIZES.body,
    color: COLORS.grayLight,
  },
});
