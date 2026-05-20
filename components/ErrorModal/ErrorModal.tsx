import { Modal, View, Text, Pressable, StyleSheet } from 'react-native';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';

type ErrorType = 'already' | 'server' | 'network';

type ErrorModalProps = {
  visible: boolean;
  type: ErrorType;
  onClose: () => void;
};

const ERROR_MESSAGES: Record<ErrorType, { title: string; message: string }> = {
  already: {
    title: '이미 참여한 이벤트',
    message: '이 이벤트는 이미 참여하셨습니다.',
  },
  server: {
    title: '서버 오류',
    message: '잠시 후 다시 시도해 주세요.',
  },
  network: {
    title: '네트워크 오류',
    message: '인터넷 연결을 확인해 주세요.',
  },
};

export default function ErrorModal({ visible, type, onClose }: ErrorModalProps) {
  const { title, message } = ERROR_MESSAGES[type];

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onClose}
    >
      <View style={styles.overlay}>
        <View style={styles.modal}>
          <Text style={styles.icon}>⚠️</Text>
          <Text style={styles.title}>{title}</Text>
          <Text style={styles.message}>{message}</Text>

          <Pressable style={styles.button} onPress={onClose}>
            <Text style={styles.buttonText}>확인</Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  modal: {
    backgroundColor: COLORS.surface,
    borderRadius: LAYOUT.cardRadius,
    borderWidth: 1,
    borderColor: COLORS.border,
    padding: 24,
    width: '100%',
    maxWidth: 320,
    alignItems: 'center',
  },
  icon: {
    fontSize: 48,
    marginBottom: 12,
  },
  title: {
    fontSize: FONT_SIZES.caption,
    fontWeight: '700',
    color: COLORS.textMain,
    marginBottom: 8,
  },
  message: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
    textAlign: 'center',
    marginBottom: 24,
  },
  button: {
    backgroundColor: COLORS.error,
    paddingVertical: 12,
    paddingHorizontal: 32,
    borderRadius: LAYOUT.borderRadius,
    minWidth: 120,
  },
  buttonText: {
    color: COLORS.textMain,
    fontSize: FONT_SIZES.caption,
    fontWeight: '600',
    textAlign: 'center',
  },
});
