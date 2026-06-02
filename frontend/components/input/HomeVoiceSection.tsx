import { StyleSheet, Text, View } from 'react-native';
import MicButton from './MicButton';
import { COLORS, FONT_SIZES } from '@/constants/theme';

type MicState = 'idle' | 'listening' | 'processing' | 'error' | 'warning';

interface HomeVoiceSectionProps {
  micState?: MicState;
  primaryHint?: string;
  subCaption?: string;
  onMicPress?: () => void;
  onMicRelease?: () => void;
}

export default function HomeVoiceSection({
  micState = 'idle',
  primaryHint = '말씀해 주세요',
  subCaption = '화면 꾹 누르기로 활성화',
  onMicPress,
  onMicRelease,
}: HomeVoiceSectionProps) {
  const hint =
    micState === 'listening'   ? '듣고 있어요...' :
    micState === 'processing'  ? '처리 중...' :
    primaryHint;

  const caption =
    micState === 'listening'  ? '말씀해 주세요. 손을 떼면 전송돼요' :
    micState === 'processing' ? '처리 중입니다...' :
    micState === 'error'      ? '다시 시도해 주세요' :
    subCaption;

  return (
    <View style={styles.wrap} pointerEvents="none">
      <View style={styles.micScale}>
        <MicButton
          state={micState}
          hint={hint}
        />
      </View>
      {caption ? <Text style={styles.subCaption}>{caption}</Text> : null}
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
