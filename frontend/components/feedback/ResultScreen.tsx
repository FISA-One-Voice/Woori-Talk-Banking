import { Image, StyleSheet, Text, View } from 'react-native';

interface ResultScreenProps {
  type: 'success' | 'error';
  label: string;
  subtitle?: string;
}

export default function ResultScreen({ type, label, subtitle }: ResultScreenProps) {
  const isSuccess = type === 'success';
  const color = isSuccess ? '#4ade80' : '#f87171';

  return (
    <View style={styles.container}>
      {isSuccess ? (
        <Image source={require('../../icon-yellow/check.png')} style={styles.icon} />
      ) : (
        <Image source={require('../../icon-yellow/close.png')} style={styles.icon} />
      )}
      <Text style={[styles.label, { color: isSuccess ? '#fff' : color }]}>
        {label}
      </Text>
      {subtitle && <Text style={styles.subtitle}>{subtitle}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    marginVertical: 16,
  },
  icon: {
    width: 64,
    height: 64,
    marginBottom: 8,
  },
  label: {
    fontSize: 32,
    fontWeight: '500',
  },
  subtitle: {
    fontSize: 24,
    color: '#555',
    marginTop: 4,
  },
});

