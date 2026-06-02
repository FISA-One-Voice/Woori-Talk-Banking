import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';

type MicState = 'idle' | 'listening' | 'processing' | 'error' | 'warning';

interface MicButtonProps {
  state?: MicState;
  hint?: string;
  onPress?: () => void;
  onPressIn?: () => void;
  onLongPress?: () => void;
  onPressOut?: () => void;
}

const STATE_COLOR: Record<MicState, string> = {
  idle:       '#FFD600',
  listening:  '#4ADE80',  // 초록: 녹음 잘 되고 있음
  processing: '#aaaaaa',  // 회색: 처리 중
  error:      '#ff4444',  // 빨강: 오류
  warning:    '#fbbf24',
};

export default function MicButton({
  state = 'idle',
  hint,
  onPress,
  onPressIn,
  onLongPress,
  onPressOut,
}: MicButtonProps) {
  const color = STATE_COLOR[state];

  return (
    <View style={styles.wrap}>
      <TouchableOpacity
        style={[
          styles.ring,
          {
            borderColor: color,
            backgroundColor: state === 'listening' ? '#002200' : state === 'error' ? '#1a0000' : '#191900',
          },
        ]}
        onPress={onPress}
        onPressIn={onPressIn}
        onLongPress={onLongPress}
        onPressOut={onPressOut}
        delayLongPress={300}
        activeOpacity={0.7}
      >
        <Text style={[styles.micIcon, { color }]}>
          {state === 'processing' ? '⏳' : '🎙'}
        </Text>
      </TouchableOpacity>
      {hint && <Text style={[styles.hint, { color }]}>{hint}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    alignItems: 'center',
    marginVertical: 12,
  },
  ring: {
    width: 64,
    height: 64,
    borderRadius: 32,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 8,
  },
  micIcon: {
    fontSize: 32,
  },
  hint: {
    fontSize: 24,
    color: '#aaa',
  },
});
