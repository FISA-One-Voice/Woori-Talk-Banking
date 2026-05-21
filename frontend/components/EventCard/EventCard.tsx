import { Pressable, StyleSheet, Text } from "react-native";
import { COLORS, FONT_SIZES, LAYOUT } from "@/constants/theme";

type EventCardProps = {
  title: string;
  date: string;
  location?: string;
  onPress?: () => void;
};

export default function EventCard({
  title,
  date,
  location,
  onPress,
}: EventCardProps) {
  return (
    <Pressable
      style={({ pressed }) => [styles.card, pressed && styles.cardPressed]}
      onPress={onPress}
    >
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.subtitle}>
        {date}
        {location ? ` · ${location}` : ""}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    padding: LAYOUT.cardPadding,
    backgroundColor: COLORS.surface,
    borderRadius: LAYOUT.borderRadius,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  cardPressed: {
    opacity: 0.7,
  },
  title: {
    fontSize: FONT_SIZES.caption,
    fontWeight: "600",
    color: COLORS.textMain,
  },
  subtitle: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
    marginTop: 4,
  },
});
