import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';

type MicState = 'idle' | 'listening' | 'error' | 'warning';

interface MicButtonProps {
  state?: MicState;
  hint?: string;
  onPress?: () => void;
}

const STATE_COLOR: Record<MicState, string> = {
  idle: '#FFD600',
  listening: '#FFD600',
  error: '#f87171',
  warning: '#fbbf24',
};

export default function MicButton({
  state = 'idle',
  hint,
  onPress,
}: MicButtonProps) {
  const color = STATE_COLOR[state];

  return (
    <View style={styles.wrap}>
      <TouchableOpacity
        style={[styles.ring, { borderColor: color, backgroundColor: state === 'idle' || state === 'listening' ? '#191900' : '#111' }]}
        onPress={onPress}
        activeOpacity={0.7}
      >
        {/* 마이크 아이콘 (텍스트 대체) */}
        <Text style={[styles.micIcon, { color }]}>🎙</Text>
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

