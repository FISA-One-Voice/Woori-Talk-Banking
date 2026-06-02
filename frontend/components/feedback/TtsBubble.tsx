import { useEffect, useRef } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { fetchTtsAudio } from '@/services/voiceService';
import { playBase64Audio } from '@/utils/audioPlayer';

type TtsBubbleVariant = 'default' | 'error' | 'warning';

interface TtsBubbleProps {
  message: string;
  variant?: TtsBubbleVariant;
  autoPlay?: boolean;
  onEnd?: () => void;
  textAlign?: 'left' | 'center';
}

const TTS_BUBBLE_VARIANT_STYLES = {
  default: {
    container: {
      backgroundColor: '#191900',
      borderColor: '#2d2800',
    },
    tag: {
      color: '#6a6300',
    },
    tagText: '음성 안내',
    message: {
      color: '#FFD600',
    },
  },
  error: {
    container: {
      backgroundColor: '#1a0000',
      borderColor: '#3d0000',
    },
    tag: {
      color: '#7a1a1a',
    },
    tagText: '오류',
    message: {
      color: '#f87171',
    },
  },
  warning: {
    container: {
      backgroundColor: '#1a1000',
      borderColor: '#3d2a00',
    },
    tag: {
      color: '#7a5000',
    },
    tagText: '확인 필요',
    message: {
      color: '#fbbf24',
    },
  },
} as const;

export default function TtsBubble({
  message,
  variant = 'default',
  autoPlay = false,
  onEnd,
  textAlign = 'left',
}: TtsBubbleProps) {
  const prevMessage = useRef<string | null>(null);

  useEffect(() => {
    if (!autoPlay) return;
    if (prevMessage.current === message) return;
    prevMessage.current = message;

    fetchTtsAudio(message)
      .then(base64 => playBase64Audio(base64))
      .then(onEnd)
      .catch(() => onEnd?.());
  }, [message, autoPlay, onEnd]);

  const variantStyles = TTS_BUBBLE_VARIANT_STYLES[variant];

  return (
    <View style={[styles.container, variantStyles.container]}>
      <Text style={[styles.tag, variantStyles.tag, { textAlign }]}>
        {variantStyles.tagText}
      </Text>
      <Text style={[styles.message, variantStyles.message, { textAlign }]}>
        {message}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    borderWidth: 0.5,
    borderRadius: 10,
    paddingVertical: 9,
    paddingHorizontal: 11,
    marginBottom: 11,
  },
  tag: {
    fontSize: 24,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginBottom: 4,
  },
  message: {
    fontSize: 32,
    lineHeight: 48,
  },
});

