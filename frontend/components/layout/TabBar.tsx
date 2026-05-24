import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';

type Tab = 'home' | 'history' | 'alarm' | 'profile';

interface TabBarProps {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
}

const TABS: { key: Tab; icon: string; label: string }[] = [
  { key: 'home', icon: '🏠', label: '홈' },
  { key: 'history', icon: '📋', label: '내역' },
  { key: 'alarm', icon: '🔔', label: '알림' },
  { key: 'profile', icon: '👤', label: '내 정보' },
];

export default function TabBar({ activeTab, onTabChange }: TabBarProps) {
  return (
    <View style={styles.bar}>
      {TABS.map((tab) => {
        const active = tab.key === activeTab;
        return (
          <TouchableOpacity
            key={tab.key}
            style={styles.item}
            onPress={() => onTabChange(tab.key)}
            activeOpacity={0.7}
          >
            <Text style={styles.icon}>{tab.icon}</Text>
            <Text style={[styles.label, active && styles.labelActive]}>
              {tab.label}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: 'row',
    justifyContent: 'space-around',
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
    fontSize: 24,
    color: '#444',
  },
  labelActive: {
    color: '#FFD600',
  },
});

