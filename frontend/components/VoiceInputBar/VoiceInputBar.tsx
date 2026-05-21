// =============================================================================
// frontend/components/VoiceInputBar/VoiceInputBar.tsx
//
// [이 컴포넌트의 역할]
// 모든 화면 하단에 고정되는 음성 입력 버튼입니다.
// 시각장애인 사용자가 화면을 탭해서 말을 시작하는 핵심 UI 컴포넌트입니다.
//
// [상태(status) 3가지]
// - 'idle'       : 기본 대기 상태. 노란 마이크 버튼이 표시됩니다.
// - 'recording'  : 녹음 중. 버튼이 빨간색으로 바뀌어 녹음 중임을 알립니다.
// - 'processing' : 서버 처리 중. 버튼이 비활성화되고 로딩 스피너가 표시됩니다.
//
// [사용 예시 - 화면 파일(app/event/index.tsx)에서]
// import VoiceInputBar, { VoiceStatus } from '@/components/VoiceInputBar';
// const [voiceStatus, setVoiceStatus] = useState<VoiceStatus>('idle');
// <VoiceInputBar status={voiceStatus} onPress={handleMicPress} />
//
// [디자이너 작성 · Tech Lead 주석 추가]
// =============================================================================

// React Native 기본 UI 컴포넌트들을 가져옵니다.
// ActivityIndicator: 로딩 중 빙글빙글 돌아가는 스피너
// Pressable: TouchableOpacity 의 최신 버전 (누름 상태를 더 정밀하게 제어)
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

// @/constants/theme → frontend/constants/theme.ts 를 가리킵니다.
// tsconfig.json 에 "@/*": ["./*"] 경로 별칭이 설정되어 있습니다.
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';

// VoiceStatus 타입을 외부에서도 쓸 수 있도록 export 합니다.
// 화면 파일에서 useState<VoiceStatus>('idle') 형태로 사용합니다.
export type VoiceStatus = 'idle' | 'recording' | 'processing';

// Props: 이 컴포넌트가 부모(화면)로부터 받는 값들의 형태 정의
type VoiceInputBarProps = {
  status: VoiceStatus;   // 현재 음성 상태 (필수)
  onPress: () => void;   // 버튼을 눌렀을 때 실행할 함수 (필수)
  disabled?: boolean;    // true 면 버튼 비활성화 (선택, 기본값: false)
};

// 각 상태에서 버튼 위에 표시할 안내 문구
// Record<VoiceStatus, string>: VoiceStatus 의 각 값마다 string 이 반드시 있어야 함
const STATUS_TEXT: Record<VoiceStatus, string> = {
  idle: '버튼을 눌러 말씀해 주세요',
  recording: '듣고 있어요...',
  processing: '처리 중...',
};

export default function VoiceInputBar({ status, onPress, disabled }: VoiceInputBarProps) {
  // 상태값을 boolean 으로 미리 계산해두면 JSX 에서 읽기 편합니다.
  const isRecording = status === 'recording';
  const isProcessing = status === 'processing';

  return (
    // 화면 하단에 고정되는 컨테이너 (position: absolute)
    <View style={styles.container}>
      {/* 현재 상태를 설명하는 텍스트. 스크린리더도 이 텍스트를 읽어줍니다. */}
      <Text style={styles.statusText}>{STATUS_TEXT[status]}</Text>

      <Pressable
        style={[
          styles.button,
          // 배열로 여러 스타일을 합칩니다. 뒤에 오는 스타일이 앞을 덮어씁니다.
          isRecording && styles.buttonRecording,  // 녹음 중: 빨간색으로 전환
          disabled && styles.buttonDisabled,      // 비활성: 반투명 처리
        ]}
        onPress={onPress}
        // 처리 중이거나 외부에서 disabled=true 로 넘기면 버튼을 누를 수 없습니다.
        disabled={disabled || isProcessing}
        accessibilityLabel={STATUS_TEXT[status]}  // 스크린리더가 읽어줄 텍스트
        accessibilityRole="button"
      >
        {/* 처리 중이면 로딩 스피너, 그 외에는 아이콘 텍스트 */}
        {isProcessing ? (
          <ActivityIndicator color={COLORS.background} />
        ) : (
          // 삼항 연산자: isRecording 이 true 면 정지 아이콘, false 면 마이크 아이콘
          <Text style={styles.icon}>{isRecording ? '⏹' : '🎤'}</Text>
        )}
      </Pressable>
    </View>
  );
}

// ── 스타일 ─────────────────────────────────────────────────────────────────────
// theme.ts 의 값을 사용해서 팀 전체가 일관된 디자인을 유지합니다.
// 색상 코드('#FFD600')를 직접 쓰지 말고 반드시 COLORS.xxx 를 사용하세요.
const styles = StyleSheet.create({
  container: {
    position: 'absolute', // 스크롤과 무관하게 항상 화면 하단에 고정
    bottom: 0,
    left: 0,
    right: 0,
    padding: 24,
    alignItems: 'center',
    backgroundColor: COLORS.surface,
    borderTopWidth: 1,
    borderTopColor: COLORS.surfaceLight,
  },
  statusText: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
    marginBottom: LAYOUT.cardPadding,
  },
  button: {
    width: 72,
    height: 72,
    borderRadius: 36,                      // 원형: 너비/높이의 절반
    backgroundColor: COLORS.highlightYellow, // 고대비 노란색 (접근성 핵심)
    justifyContent: 'center',
    alignItems: 'center',
  },
  buttonRecording: {
    backgroundColor: COLORS.error,  // 녹음 중: 빨간색
  },
  buttonDisabled: {
    opacity: 0.5,  // 비활성: 50% 투명
  },
  icon: {
    fontSize: FONT_SIZES.button,
  },
});
