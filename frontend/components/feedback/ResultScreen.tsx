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
      <View style={[styles.circle, { borderColor: color }]}>
        {isSuccess ? (
          <Image source={require('../../icon-yellow/check.png')} style={styles.icon} />
        ) : (
          <Image source={require('../../icon-yellow/close.png')} style={styles.icon} />
        )}
      </View>
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
  circle: {
    width: 56,
    height: 56,
    borderRadius: 28,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 8,
  },
  icon: {
    width: 32,
    height: 32,
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

