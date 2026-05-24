import { useEffect, useRef } from 'react';
import { Animated, StyleSheet, View } from 'react-native';

export default function LoadingDots() {
  const anims = useRef([
    new Animated.Value(1),
    new Animated.Value(0.2),
    new Animated.Value(0.2),
  ]).current;

  useEffect(() => {
    const loops = anims.map((anim, i) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(i * 200),
          Animated.timing(anim, { toValue: 1, duration: 300, useNativeDriver: true }),
          Animated.timing(anim, { toValue: 0.2, duration: 300, useNativeDriver: true }),
          Animated.delay((anims.length - i - 1) * 200),
        ])
      )
    );

    loops.forEach((l) => l.start());
    return () => loops.forEach((l) => l.stop());
  }, []);

  return (
    <View style={styles.row}>
      {anims.map((anim, i) => (
        <Animated.View key={i} style={[styles.dot, { opacity: anim }]} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 6,
    marginVertical: 14,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#FFD600',
  },
});

