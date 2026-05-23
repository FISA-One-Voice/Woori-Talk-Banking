import { StyleSheet, View } from 'react-native';

interface StepIndicatorProps {
  total: number;
  current: number;
}

export default function StepIndicator({ total, current }: StepIndicatorProps) {
  return (
    <View style={styles.row}>
      {Array.from({ length: total }, (_, i) => {
        const done = i < current;
        return (
          <View
            key={i}
            style={[
              styles.dot,
              done ? styles.dotDone : styles.dotPending,
            ]}
          />
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 6,
    marginBottom: 12,
  },
  dot: {
    height: 6,
    borderRadius: 3,
  },
  dotDone: {
    width: 14,
    backgroundColor: '#FFD600',
  },
  dotPending: {
    width: 6,
    backgroundColor: '#222',
  },
});

