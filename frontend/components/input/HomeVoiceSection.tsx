import { StyleSheet, Text, View } from 'react-native';
import MicButton from './MicButton';
import { COLORS, FONT_SIZES } from '@/constants/theme';

type MicState = 'idle' | 'listening' | 'error' | 'warning';

interface HomeVoiceSectionProps {
  micState?: MicState;
  primaryHint?: string;
  subCaption?: string;
  onMicPress?: () => void;
}

export default function HomeVoiceSection({
  micState = 'idle',
  primaryHint = '말씀해 주세요',
  subCaption = '화면 꾹 누르기로 활성화',
  onMicPress,
}: HomeVoiceSectionProps) {
  return (
    <View style={styles.wrap}>
      <View style={styles.micScale}>
        <MicButton state={micState} hint={primaryHint} onPress={onMicPress} />
      </View>
      {subCaption ? <Text style={styles.subCaption}>{subCaption}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    alignItems: 'center',
    marginVertical: 12,
  },
  micScale: {
    transform: [{ scale: 1.35 }],
    marginBottom: 4,
  },
  subCaption: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
    marginTop: 8,
  },
});
