import { Image, StyleSheet, Text as RNText, View } from 'react-native';
import { COLORS, FONT_SIZES } from '@/constants/theme';

export default function FingerprintIcon() {
  return (
    <View style={styles.wrap}>
      <View style={styles.ring}>
        <Image source={require('../../icon-yellow/fingerprint.png')} style={styles.icon} />
      </View>
      <RNText style={styles.label}>생체 인식 대기</RNText>
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
    width: 48,
    height: 48,
  },
  label: {
    fontSize: FONT_SIZES.body,
    color: COLORS.grayLight,
  },
});
