import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';

interface TopBarProps {
  variant: 'logo' | 'back' | 'action' | 'title';
  title?: string;
  onBack?: () => void;
  actionLabel?: string;
  onAction?: () => void;
}

export default function TopBar({
  variant,
  title,
  onBack,
  actionLabel,
  onAction,
}: TopBarProps) {
  return (
    <View style={styles.container}>
      {variant === 'logo' && (
        <Text style={styles.appName}>우리톡뱅킹</Text>
      )}

      {variant === 'title' && (
        <Text style={[styles.title, styles.titleCentered]}>{title}</Text>
      )}

      {variant === 'back' && (
        <>
          <TouchableOpacity style={styles.backBtn} onPress={onBack}>
            <Text style={styles.backArrow}>←</Text>
          </TouchableOpacity>
          <Text style={styles.title}>{title}</Text>
          <View style={styles.spacer} />
        </>
      )}

      {variant === 'action' && (
        <>
          <Text style={styles.appName}>우리톡뱅킹</Text>
          <TouchableOpacity style={styles.actionBtn} onPress={onAction}>
            <Text style={styles.actionLabel}>{actionLabel}</Text>
          </TouchableOpacity>
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 0.5,
    borderBottomColor: '#222',
    marginBottom: 14,
  },
  appName: {
    fontSize: 32,
    fontWeight: '500',
    color: '#FFD600',
  },
  title: {
    fontSize: 32,
    fontWeight: '500',
    color: '#fff',
  },
  titleCentered: {
    flex: 1,
    textAlign: 'center',
  },
  backBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 0.5,
    borderColor: '#2a2a2a',
    backgroundColor: '#1a1a1a',
    alignItems: 'center',
    justifyContent: 'center',
  },
  backArrow: {
    fontSize: 28,
    color: '#aaa',
  },
  spacer: {
    width: 36,
  },
  actionBtn: {
    borderRadius: 6,
    borderWidth: 0.5,
    borderColor: '#2a2a2a',
    backgroundColor: '#1a1a1a',
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  actionLabel: {
    fontSize: 24,
    color: '#555',
  },
});

