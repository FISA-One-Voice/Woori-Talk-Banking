import { FingerprintIcon, StatusBadge } from '@/components/feedback';
import { ActionButton } from '@/components/display';
import { StyleSheet, View } from 'react-native';

interface AsvStepViewProps {
  loading: boolean;
  onDevSkip?: () => void;
}

export function AsvStepView({ loading, onDevSkip }: AsvStepViewProps) {
  return (
    <View style={styles.wrap}>
      <FingerprintIcon />
      <StatusBadge text="음성 인증 중" />
      {__DEV__ && onDevSkip && (
        <ActionButton
          label="[개발] 인증 건너뛰기"
          variant="outline"
          onPress={onDevSkip}
          disabled={loading}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 12, alignItems: 'center' },
});
