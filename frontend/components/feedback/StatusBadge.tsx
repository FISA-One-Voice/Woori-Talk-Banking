import { StyleSheet, Text, View } from 'react-native';

interface StatusBadgeProps {
  text: string;
  variant?: 'default' | 'error';
}

export default function StatusBadge({ text, variant = 'default' }: StatusBadgeProps) {
  const color = variant === 'error' ? '#f87171' : '#FFD600';
  const bg = variant === 'error' ? '#1a0000' : '#191900';
  const border = variant === 'error' ? '#3d0000' : '#FFD600';

  return (
    <View style={[styles.badge, { backgroundColor: bg, borderColor: border }]}>
      <View style={[styles.dot, { backgroundColor: color }]} />
      <Text style={[styles.text, { color }]}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    borderWidth: 0.5,
    borderRadius: 14,
    paddingVertical: 5,
    paddingHorizontal: 10,
    alignSelf: 'center',
    marginBottom: 12,
  },
  dot: {
    width: 7,
    height: 7,
    borderRadius: 3.5,
  },
  text: {
    fontSize: 28,
    fontWeight: '500',
  },
});

