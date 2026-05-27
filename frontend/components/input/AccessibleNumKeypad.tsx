import { useState } from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import * as Speech from 'expo-speech';

interface AccessibleNumKeypadProps {
  length: 4 | 6;
  onComplete: (pin: string) => void;
  onFocusDigit?: (digit: string) => void;
  masked?: boolean;
}

const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '', '0', '삭제'];

export default function AccessibleNumKeypad({
  length,
  onComplete,
  onFocusDigit,
  masked: _masked = true,
}: AccessibleNumKeypadProps) {
  const [pin, setPin] = useState('');

  const handleKey = (key: string) => {
    if (key === '삭제') {
      setPin((p) => p.slice(0, -1));
      return;
    }
    if (key === '') return;

    const next = pin + key;
    setPin(next);
    if (next.length === length) {
      onComplete(next);
      setPin('');
    }
  };

  const handleFocus = (key: string) => {
    if (!key || key === '삭제') return;
    Speech.speak(key, { language: 'ko-KR' });
    onFocusDigit?.(key);
  };

  return (
    <View>
      {/* PIN 점 표시 */}
      <View style={styles.dotsRow}>
        {Array.from({ length }, (_, i) => (
          <View
            key={i}
            style={[styles.pinDot, i < pin.length && styles.pinDotFilled]}
          />
        ))}
      </View>

      {/* 숫자 패드 */}
      <View style={styles.grid}>
        {KEYS.map((key, i) => (
          <TouchableOpacity
            key={i}
            style={[styles.key, key === '' && styles.keyEmpty]}
            onPress={() => handleKey(key)}
            onFocus={() => handleFocus(key)}
            accessible
            accessibilityLabel={key || undefined}
            disabled={key === ''}
          >
            <Text style={[styles.keyText, key === '삭제' && styles.keyDelete]}>
              {key}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  dotsRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 10,
    marginBottom: 16,
  },
  pinDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    borderWidth: 1.5,
    borderColor: '#444',
  },
  pinDotFilled: {
    backgroundColor: '#FFD600',
    borderColor: '#FFD600',
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: 6,
  },
  key: {
    width: '30%',
    backgroundColor: '#1a1a1a',
    borderWidth: 0.5,
    borderColor: '#252525',
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: 'center',
  },
  keyEmpty: {
    backgroundColor: 'transparent',
    borderWidth: 0,
  },
  keyText: {
    fontSize: 28,
    fontWeight: '500',
    color: '#fff',
  },
  keyDelete: {
    fontSize: 24,
    color: '#555',
  },
});

