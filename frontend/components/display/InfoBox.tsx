import { StyleSheet, Text, View } from 'react-native';

type InfoBoxState = 'empty' | 'ok' | 'default' | 'big';

interface InfoBoxProps {
  label: string;
  value?: string;
  state?: InfoBoxState;
}

const VALUE_COLOR: Record<InfoBoxState, string> = {
  empty: '#333',
  ok: '#FFD600',
  default: '#fff',
  big: '#fff',
};

export default function InfoBox({ label, value, state = 'default' }: InfoBoxProps) {
  const isEmpty = state === 'empty' || !value;

  return (
    <View style={styles.box}>
      <Text style={styles.label}>{label}</Text>
      <Text
        style={[
          styles.value,
          { color: isEmpty ? '#333' : VALUE_COLOR[state] },
          state === 'big' && styles.valueBig,
        ]}
      >
        {value || '미입력'}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    backgroundColor: '#1a1a1a',
    borderWidth: 0.5,
    borderColor: '#252525',
    borderRadius: 8,
    paddingVertical: 9,
    paddingHorizontal: 12,
    marginBottom: 8,
  },
  label: {
    fontSize: 24,
    color: '#555',
    marginBottom: 3,
  },
  value: {
    fontSize: 28,
    fontWeight: '500',
  },
  valueBig: {
    fontSize: 36,
  },
});

