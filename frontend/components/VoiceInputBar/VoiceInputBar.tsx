import {
    ActivityIndicator,
    Pressable,
    StyleSheet,
    Text,
    View,
} from "react-native";
import { COLORS, FONT_SIZES, LAYOUT } from "@/constants/theme";

export type VoiceStatus = "idle" | "recording" | "processing";

type VoiceInputBarProps = {
  status: VoiceStatus;
  onPress: () => void;
  disabled?: boolean;
};

const STATUS_TEXT: Record<VoiceStatus, string> = {
  idle: "버튼을 눌러 말씀해 주세요",
  recording: "듣고 있어요...",
  processing: "처리 중...",
};

export default function VoiceInputBar({
  status,
  onPress,
  disabled,
}: VoiceInputBarProps) {
  const isRecording = status === "recording";
  const isProcessing = status === "processing";

  return (
    <View style={styles.container}>
      <Text style={styles.statusText}>{STATUS_TEXT[status]}</Text>

      <Pressable
        style={[
          styles.button,
          isRecording && styles.buttonRecording,
          disabled && styles.buttonDisabled,
        ]}
        onPress={onPress}
        disabled={disabled || isProcessing}
      >
        {isProcessing ? (
          <ActivityIndicator color={COLORS.background} />
        ) : (
          <Text style={styles.icon}>{isRecording ? "⏹" : "🎤"}</Text>
        )}
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    padding: 24,
    alignItems: "center",
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
    borderRadius: 36,
    backgroundColor: COLORS.highlightYellow,
    justifyContent: "center",
    alignItems: "center",
  },
  buttonRecording: {
    backgroundColor: COLORS.error,
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  icon: {
    fontSize: FONT_SIZES.button,
  },
});
