import { useEffect, useRef } from 'react';
import { Animated, StyleSheet, View } from 'react-native';

interface VoiceWaveAnimationProps {
  isActive?: boolean;
  barCount?: number;
  audioLevel?: number; // -160 to 0 (dB)
}

export default function VoiceWaveAnimation({
  isActive = true,
  barCount = 8,
  audioLevel = -160,
}: VoiceWaveAnimationProps) {
  const anims = useRef(
    Array.from({ length: barCount }, () => new Animated.Value(0.3))
  ).current;

  useEffect(() => {
    if (!isActive) {
      anims.forEach((a) => a.setValue(0.3));
      return;
    }

    // 보통 말소리는 -40dB ~ -10dB 사이에 분포합니다.
    let floor = -40; 
    let range = 40; 
    
    let raw = (audioLevel - floor) / range;
    if (raw < 0) raw = 0;
    if (raw > 1) raw = 1;

    // 파동이 0.3배 ~ 2.5배까지 아주 역동적으로 춤추도록 설정
    let normalized = 0.3 + (raw * 2.2);

    // 각 바마다 랜덤성을 주어 진짜 이퀄라이저처럼 보이게 만듦
    const animations = anims.map((anim) => {
      // 소리가 들어올 때만 위아래로 미친듯이 요동치게 만듦 (최대 ±0.5 랜덤)
      const randomJitter = raw > 0.05 ? (Math.random() * 1.0 - 0.5) : 0;
      let targetScale = normalized + randomJitter;
      if (targetScale < 0.3) targetScale = 0.3;

      return Animated.timing(anim, {
        toValue: targetScale,
        duration: 80, // 80ms로 매우 민감하고 빠르게 반응
        useNativeDriver: true,
      });
    });

    Animated.parallel(animations).start();
  }, [isActive, audioLevel]);

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

