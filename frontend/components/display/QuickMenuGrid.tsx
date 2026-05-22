import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';

interface QuickMenuItem {
  icon: string;
  label: string;
  onPress: () => void;
}

interface QuickMenuGridProps {
  items: QuickMenuItem[];
}

export default function QuickMenuGrid({ items }: QuickMenuGridProps) {
  return (
    <View style={styles.grid}>
      {items.map((item, i) => (
        <TouchableOpacity key={i} style={styles.btn} onPress={item.onPress} activeOpacity={0.7}>
          <Text style={styles.icon}>{item.icon}</Text>
          <Text style={styles.label}>{item.label}</Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 12,
  },
  btn: {
    width: '47%',
    backgroundColor: '#1a1a1a',
    borderWidth: 0.5,
    borderColor: '#252525',
    borderRadius: 10,
    padding: 12,
    gap: 4,
  },
  icon: {
    fontSize: 24,
  },
  label: {
    fontSize: 28,
    fontWeight: '500',
    color: '#fff',
  },
  cmd: {
    fontSize: 24,
    color: '#444',
  },
});

