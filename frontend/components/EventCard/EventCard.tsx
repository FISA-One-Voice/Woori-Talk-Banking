// =============================================================================
// frontend/components/EventCard/EventCard.tsx
//
// [이 컴포넌트의 역할]
// 이벤트 목록 화면에서 이벤트 하나를 카드 형태로 보여줍니다.
// 카드를 누르면 해당 이벤트 상세 화면으로 이동합니다.
//
// [사용 예시 - 화면 파일(app/event/index.tsx)에서]
// import EventCard from '@/components/EventCard';
// <EventCard
//   title={event.title}
//   date={`${formatDate(event.start_date)} ~ ${formatDate(event.end_date)}`}
//   onPress={() => router.push(`/event/${event.id}`)}
// />
//
// [디자이너 작성 · Tech Lead 주석 추가]
// =============================================================================

import { Pressable, StyleSheet, Text } from 'react-native';

import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';

// Props: 이 컴포넌트가 부모(화면)로부터 받는 값들의 형태 정의
type EventCardProps = {
  title: string;       // 이벤트 제목 (필수)
  date: string;        // 기간 문자열 (필수). 예: "2024년 1월 1일 ~ 1월 31일"
  location?: string;   // 장소 (선택). 있으면 날짜 옆에 " · 장소명" 형태로 표시
  onPress?: () => void; // 카드를 눌렀을 때 실행할 함수 (선택)
};

export default function EventCard({ title, date, location, onPress }: EventCardProps) {
  return (
    <Pressable
      style={({ pressed }) => [styles.card, pressed && styles.cardPressed]}
      onPress={onPress}
    >
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.subtitle}>
        {date}
        {location ? ` · ${location}` : ''}
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
    fontWeight: '600',
    color: COLORS.textMain,
  },
  subtitle: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
    marginTop: 4,
  },
});
