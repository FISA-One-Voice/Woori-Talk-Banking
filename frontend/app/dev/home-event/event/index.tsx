// =============================================================================
// app/dev/home-event/event/index.tsx   (SCR-007 목록)
// =============================================================================

import { ActionButton } from '@/components/display';
import { TtsBubble } from '@/components/feedback';
import { TopBar } from '@/components/layout';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import { apiClient, type ApiResponse } from '@/utils/api';
import { useScreenAnnounce } from '@/hooks/useScreenAnnounce';
import { useMic } from '@/context/MicContext';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Platform,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';

// ── 타입 ─────────────────────────────────────────────────────────────────────

interface EventItem {
  event_id: string;
  title: string;
  description: string | null;
  banner_image_url: string | null;
  is_active: boolean;
  start_at: string;
  end_at: string;
}

// ── 헬퍼 ─────────────────────────────────────────────────────────────────────

function formatEndDate(dateStr: string): string {
  const d = new Date(dateStr);
  return `~${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`;
}

// ── 이벤트 행 ─────────────────────────────────────────────────────────────────

function EventRow({ event }: { event: EventItem }) {
  const { activateMic } = useMic();

  return (
    <TouchableOpacity
      style={rowStyles.container}
      onPress={() => router.push(`/dev/home-event/event/${event.event_id}`)}
      onLongPress={activateMic}
      delayLongPress={600}
      activeOpacity={0.7}
    >
      <View style={rowStyles.content}>
        <Text style={rowStyles.title} numberOfLines={1}>{event.title}</Text>
        {event.description && (
          <Text style={rowStyles.desc} numberOfLines={1}>{event.description}</Text>
        )}
        <Text style={rowStyles.date}>{formatEndDate(event.end_at)}</Text>
      </View>
      <Text style={rowStyles.arrow}>›</Text>
    </TouchableOpacity>
  );
}

const rowStyles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: COLORS.surface,
    borderWidth: 0.5,
    borderColor: COLORS.border,
    borderRadius: LAYOUT.borderRadius,
    paddingVertical: 16,
    paddingHorizontal: 16,
    marginBottom: 10,
  },
  content: { flex: 1 },
  title: {
    fontSize: FONT_SIZES.body,
    color: COLORS.textMain,
    fontWeight: '600',
    marginBottom: 4,
  },
  desc: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.highlightYellow,
    marginBottom: 4,
  },
  date: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
  },
  arrow: {
    fontSize: 24,
    color: COLORS.grayMedium,
    marginLeft: 8,
  },
});

// ── 메인 화면 ─────────────────────────────────────────────────────────────────

type Screen = 'loading' | 'list' | 'empty';

export default function EventListScreen() {
  const [screen, setScreen] = useState<Screen>('loading');
  const [events, setEvents] = useState<EventItem[]>([]);

  useScreenAnnounce('이벤트 목록 화면입니다.');

  useEffect(() => {
    apiClient
      .get<ApiResponse<{ events: EventItem[]; total: number }>>('/events')
      .then((res) => {
        const list = res.data.success && res.data.data
          ? res.data.data.events
          : [];
        setEvents(list);
        setScreen(list.length > 0 ? 'list' : 'empty');
      })
      .catch(() => setScreen('empty'));
  }, []);

  const ttsMessage =
    screen === 'loading' ? '이벤트 목록을 불러오고 있습니다.' :
    screen === 'empty'   ? '진행 중인 이벤트가 없습니다.'     :
    `진행 중인 이벤트 ${events.length}개가 있습니다.`;

  return (
    <View style={styles.root}>
      <View style={styles.body}>
        <TopBar variant="back" title="이벤트" onBack={() => router.back()} />
        <TtsBubble message={ttsMessage} autoPlay />

        {screen === 'loading' && (
          <View style={styles.center}>
            <ActivityIndicator size="large" color={COLORS.highlightYellow} />
          </View>
        )}

        {screen === 'list' && (
          <ScrollView
            style={styles.scroll}
            contentContainerStyle={styles.scrollContent}
            showsVerticalScrollIndicator={false}
          >
            {events.map((event) => (
              <EventRow key={event.event_id} event={event} />
            ))}
          </ScrollView>
        )}

        {screen === 'empty' && (
          <View style={styles.bottom}>
            <ActionButton
              label="홈으로 돌아가기"
              variant="outline"
              onPress={() => router.replace('/dev/home-event')}
            />
          </View>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: COLORS.background,
    paddingTop: Platform.OS === 'android' ? StatusBar.currentHeight ?? 24 : 0,
  },
  body: {
    flex: 1,
    paddingHorizontal: LAYOUT.paddingMedium,
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  scroll: { flex: 1 },
  scrollContent: { paddingBottom: 24 },
  bottom: {
    flex: 1,
    justifyContent: 'flex-end',
    paddingBottom: 32,
  },
});
