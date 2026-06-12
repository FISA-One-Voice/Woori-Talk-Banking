import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';

interface TabBarProps {
  onLogout: () => void;
}

export default function TabBar({ onLogout }: TabBarProps) {
  return (
    <View style={styles.bar}>
      <TouchableOpacity style={styles.item} onPress={onLogout} activeOpacity={0.7}>
        <Text style={styles.icon}>🚪</Text>
        <Text style={styles.label}>로그아웃</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    alignItems: 'center',
    paddingTop: 10,
    borderTopWidth: 0.5,
    borderTopColor: '#1e1e1e',
  },
  item: {
    alignItems: 'center',
    gap: 3,
  },
  icon: {
    fontSize: 24,
  },
  label: {
    fontSize: 14,
    color: '#ff6b6b',
  },
});

