import { Pressable, StyleSheet, Text, View } from "react-native";
import { COLORS, FONT_SIZES, LAYOUT } from "@/constants/theme";

type SuccessScreenProps = {
  eventName: string;
  message?: string;
  onConfirm: () => void;
};

export default function SuccessScreen({
  eventName,
  message = "성공적으로 참여했습니다",
  onConfirm,
}: SuccessScreenProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.icon}>✅</Text>
      <Text style={styles.title}>참여 완료</Text>
      <Text style={styles.eventName}>{eventName}</Text>
      <Text style={styles.message}>{message}</Text>

      <Pressable style={styles.button} onPress={onConfirm}>
        <Text style={styles.buttonText}>확인</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
    backgroundColor: COLORS.background,
  },
  icon: {
    fontSize: 64,
    marginBottom: 16,
  },
  title: {
    fontSize: FONT_SIZES.body,
    fontWeight: "700",
    color: COLORS.textMain,
    marginBottom: 8,
  },
  eventName: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMuted,
    marginBottom: 4,
  },
  message: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
    marginBottom: 32,
  },
  button: {
    backgroundColor: COLORS.highlightYellow,
    paddingVertical: 14,
    paddingHorizontal: 48,
    borderRadius: LAYOUT.borderRadius,
  },
  buttonText: {
    color: COLORS.background,
    fontSize: FONT_SIZES.button,
    fontWeight: "600",
  },
});
