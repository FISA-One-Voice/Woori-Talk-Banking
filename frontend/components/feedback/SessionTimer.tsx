import { useEffect, useRef, useState } from 'react';
import { StyleSheet, Text } from 'react-native';
import { COLORS, FONT_SIZES } from '@/constants/theme';

interface SessionTimerProps {
  durationSeconds?: number;
  onExpire?: () => void;
}

export default function SessionTimer({ durationSeconds = 300, onExpire }: SessionTimerProps) {
  const [remaining, setRemaining] = useState(durationSeconds);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    intervalRef.current = setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(intervalRef.current!);
          onExpire?.();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  const mm = String(Math.floor(remaining / 60)).padStart(2, '0');
  const ss = String(remaining % 60).padStart(2, '0');

  return (
    <Text style={styles.text}>세션 만료까지 {mm}:{ss}</Text>
  );
}

const styles = StyleSheet.create({
  text: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayDark,
    textAlign: 'center',
    marginVertical: 8,
  },
});
