import { useState } from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import * as Speech from 'expo-speech';

interface AccessibleNumKeypadProps {
  length: 4 | 6 | 11;
  onComplete: (value: string) => void;
  onFocusDigit?: (digit: string) => void;
  masked?: boolean;
  mode?: 'pin' | 'phone';
}

const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '', '0', '삭제'];

export default function AccessibleNumKeypad({
  length,
  onComplete,
  onFocusDigit,
  masked: _masked = true,
  mode = 'pin',
}: AccessibleNumKeypadProps) {
  const [pin, setPin] = useState('');

  const formattedPhone = () => {
    if (pin.length <= 3) return pin;
    if (pin.length <= 7) return `${pin.slice(0, 3)}-${pin.slice(3)}`;
    return `${pin.slice(0, 3)}-${pin.slice(3, 7)}-${pin.slice(7, 11)}`;
  };

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
      {/* 입력 표시 영역 */}
      {mode === 'phone' ? (
        <View style={styles.phoneRow}>
          <Text style={[styles.phoneText, pin.length === 0 && styles.phonePlaceholder]}>
            {pin.length === 0 ? '010-0000-0000' : formattedPhone()}
          </Text>
        </View>
      ) : (
        <View style={styles.dotsRow}>
          {Array.from({ length }, (_, i) => (
            <View
              key={i}
              style={[styles.pinDot, i < pin.length && styles.pinDotFilled]}
            />
          ))}
        </View>
      )}

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
  phoneRow: {
    alignItems: 'center',
    marginBottom: 16,
    paddingVertical: 12,
    backgroundColor: '#1A1A1A',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#2A2A2A',
  },
  phoneText: {
    fontSize: 32,
    color: '#FFF080',
    fontWeight: '600',
    letterSpacing: 2,
  },
  phonePlaceholder: {
    color: '#777777',
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

