import { useEffect, useRef } from 'react';
import { Animated, StyleSheet, View } from 'react-native';

interface VoiceWaveAnimationProps {
  isActive?: boolean;
  barCount?: number;
}

export default function VoiceWaveAnimation({
  isActive = true,
  barCount = 8,
}: VoiceWaveAnimationProps) {
  const anims = useRef(
    Array.from({ length: barCount }, () => new Animated.Value(0.3))
  ).current;

  useEffect(() => {
    if (!isActive) {
      anims.forEach((a) => a.setValue(0.3));
      return;
    }

    const loops = anims.map((anim, i) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(i * 80),
          Animated.timing(anim, { toValue: 1, duration: 300, useNativeDriver: true }),
          Animated.timing(anim, { toValue: 0.3, duration: 300, useNativeDriver: true }),
        ])
      )
    );

    loops.forEach((l) => l.start());
    return () => loops.forEach((l) => l.stop());
  }, [isActive]);

  const baseHeights = [10, 24, 36, 16, 28, 12, 32, 20];

  return (
    <View style={styles.wrap}>
      {anims.map((anim, i) => (
        <Animated.View
          key={i}
          style={[
            styles.bar,
            {
              height: baseHeights[i % baseHeights.length],
              transform: [{ scaleY: anim }],
            },
          ]}
        />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    marginVertical: 12,
    height: 44,
  },
  bar: {
    width: 4,
    backgroundColor: '#FFD600',
    borderRadius: 2,
  },
});

