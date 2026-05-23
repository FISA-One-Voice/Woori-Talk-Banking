import { StyleSheet, Text, TouchableOpacity } from 'react-native';

type ButtonVariant = 'primary' | 'outline' | 'destructive';

interface ActionButtonProps {
  label: string;
  variant?: ButtonVariant;
  onPress: () => void;
  disabled?: boolean;
  flex?: number;
}

const ACTION_BUTTON_VARIANT_STYLES = {
  primary: {
    container: { backgroundColor: '#FFD600', borderWidth: 0 },
    text: { color: '#111' },
  },
  outline: {
    container: { backgroundColor: 'transparent', borderWidth: 0.5, borderColor: '#333' },
    text: { color: '#aaa' },
  },
  destructive: {
    container: { backgroundColor: '#f87171', borderWidth: 0 },
    text: { color: '#fff' },
  },
} as const;

export default function ActionButton({
  label,
  variant = 'primary',
  onPress,
  disabled = false,
  flex,
}: ActionButtonProps) {
  const variantStyles = ACTION_BUTTON_VARIANT_STYLES[variant];

  return (
    <TouchableOpacity
      style={[
        styles.base,
        variantStyles.container,
        flex !== undefined && { flex },
        disabled && styles.disabled,
      ]}
      onPress={onPress}
      disabled={disabled}
      activeOpacity={0.7}
    >
      <Text style={[styles.label, variantStyles.text]}>{label}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  base: {
    borderRadius: 8,
    paddingVertical: 13,
    paddingHorizontal: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  label: {
    fontSize: 28,
    fontWeight: '500',
  },
  disabled: {
    opacity: 0.4,
  },
});

