import { StyleSheet, Text, View } from "react-native";
import { COLORS, FONT_SIZES } from "@/constants/theme";

type EmptyStateProps = {
  message?: string;
  icon?: string;
};

export default function EmptyState({
  message = "이벤트가 없습니다",
  icon = "📭",
}: EmptyStateProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.icon}>{icon}</Text>
      <Text style={styles.message}>{message}</Text>
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
    fontSize: 48,
    marginBottom: 16,
  },
  message: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
  },
});
