// =============================================================================
// frontend/components/ErrorModal/ErrorModal.tsx
//
// [이 컴포넌트의 역할]
// 오류가 발생했을 때 화면 위에 띄우는 팝업(모달) 컴포넌트입니다.
// 오류 종류(type)에 따라 제목과 메시지가 자동으로 바뀝니다.
//
// [오류 종류 3가지]
// - 'already' : 이미 참여한 이벤트 (백엔드 error_code: ALREADY_PARTICIPATED)
// - 'server'  : 서버 내부 오류 (백엔드 5xx 오류)
// - 'network' : 인터넷 연결 문제 (백엔드 서버에 아예 연결 못한 경우)
//
// [사용 예시 - 화면 파일(app/event/[id].tsx)에서]
// import ErrorModal from '@/components/ErrorModal';
// <ErrorModal
//   visible={errorType !== null}
//   type={errorType ?? 'server'}
//   onClose={() => setErrorType(null)}
// />
//
// [백엔드 error_code 와 ErrorType 의 매핑]
// 'ALREADY_PARTICIPATED' → 'already'
// 'NETWORK_ERROR'        → 'network'
// 그 외                  → 'server'
//
// [디자이너 작성 · Tech Lead 주석 추가]
// =============================================================================

import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';

import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';

// ErrorType: 이 컴포넌트가 처리할 수 있는 오류 종류
type ErrorType = 'already' | 'server' | 'network';

// Props: 이 컴포넌트가 부모(화면)로부터 받는 값들의 형태 정의
type ErrorModalProps = {
  visible: boolean;    // true 이면 모달이 화면에 표시됩니다.
  type: ErrorType;     // 오류 종류 (어떤 메시지를 보여줄지 결정)
  onClose: () => void; // 확인 버튼을 눌렀을 때 실행할 함수 (모달을 닫는 역할)
};

// 오류 종류별 제목과 메시지를 미리 정의합니다.
// type 값 하나로 제목과 메시지를 동시에 가져올 수 있습니다.
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
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
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
