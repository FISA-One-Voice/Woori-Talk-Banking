// =============================================================================
// components/screens/HomeScreen.tsx
//
// [이 파일의 역할]
// 홈 화면 UI 컴포넌트 (SCR-003).
// 어디로 이동할지는 props(콜백)로 받아서 처리합니다.
// 컴포넌트 자체는 경로를 모릅니다 → 어떤 환경에서도 재사용 가능합니다.
//
// [사용 방법]
// ① dev 테스트용 (app/dev/home/index.tsx):
//    <HomeScreen
//      onEventBannerPress={(id) => router.push(`/dev/event/${id}`)}
//      onEventMenuPress={() => router.push('/dev/event')}
//    />
//
// ② 실제 앱 조립 시 (app/home/index.tsx):
//    <HomeScreen
//      onEventBannerPress={(id) => router.push(`/event/${id}`)}
//      onEventMenuPress={() => router.push('/event')}
//      onTransferPress={() => router.push('/transfer')}
//      onAssetPress={() => router.push('/asset')}
//      onAutoTransferPress={() => router.push('/auto-transfer')}
//    />
// =============================================================================

import { VoiceQuickMenuGrid } from '@/components/display';
import type { VoiceQuickMenuItem } from '@/components/display';
import { TtsBubble } from '@/components/feedback';
import { HomeVoiceSection } from '@/components/input';
import { TabBar, TopBar } from '@/components/layout';
import { useMic } from '@/context/MicContext';
import { HOME_MENU_ITEMS } from '@/constants/homeMenu';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import { apiClient, type ApiResponse } from '@/utils/api';
import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import {
  Platform,
  Pressable,
  StatusBar,
  StyleSheet,
  Text,
  View,
} from 'react-native';


// ── 타입 ─────────────────────────────────────────────────────────────────────

interface EventItem {
  event_id: string;
  title: string;
  description: string | null;
}

export interface HomeScreenProps {
  onEventBannerPress: (eventId: string) => void;
  onEventMenuPress: () => void;
  onTransferPress?: () => void;
  onAssetPress?: () => void;
  onAutoTransferPress?: () => void;
}

// ── 인사말은 앱 실행 후 최초 1회만 재생 ──────────────────────────────────────
let hasGreeted = false;

// ── 이벤트 배너 ───────────────────────────────────────────────────────────────

function EventBanner({ event, onPress }: { event: EventItem; onPress: () => void }) {
  const { activateMic } = useMic();
  return (
    <Pressable
      style={bannerStyles.container}
      onPress={onPress}
      onLongPress={activateMic}
      delayLongPress={600}
    >
      <View style={bannerStyles.row}>
        <View style={bannerStyles.badge}>
          <Text style={bannerStyles.badgeText}>이벤트</Text>
        </View>
        <Text style={bannerStyles.title} numberOfLines={1}>{event.title}</Text>
      </View>
      {event.description && (
        <Text style={bannerStyles.desc} numberOfLines={1}>{event.description}</Text>
      )}
    </Pressable>
  );
}

const bannerStyles = StyleSheet.create({
  container: {
    backgroundColor: COLORS.yellowBg,
    borderWidth: 1,
    borderColor: COLORS.highlightYellow,
    borderRadius: LAYOUT.borderRadius + 2,
    paddingVertical: 12,
    paddingHorizontal: 14,
    marginBottom: 12,
    gap: 4,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  badge: {
    backgroundColor: COLORS.highlightYellow,
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  badgeText: {
    fontSize: FONT_SIZES.caption - 2,
    fontWeight: '700',
    color: '#111111',
  },
  title: {
    fontSize: FONT_SIZES.body,
    fontWeight: '600',
    color: COLORS.highlightYellow,
    flex: 1,
  },
  desc: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayLight,
  },
});

// ── 메인 컴포넌트 ─────────────────────────────────────────────────────────────

export default function HomeScreen({
  onEventBannerPress,
  onEventMenuPress,
  onTransferPress,
  onAssetPress,
  onAutoTransferPress,
}: HomeScreenProps) {
  const { voiceState, activateMic, stopMic } = useMic();
  const [firstEvent, setFirstEvent] = useState<EventItem | null>(null);
  const [ttsReady, setTtsReady] = useState(false);
  const [idleAutoPlay, setIdleAutoPlay] = useState(false);

  // ── 이벤트 로드 ────────────────────────────────────────────────────────────
  useEffect(() => {
    apiClient
      .get<ApiResponse<{ events: EventItem[]; total: number }>>('/events')
      .then((res) => {
        if (res.data.success && res.data.data) {
          setFirstEvent(res.data.data.events[0] ?? null);
        }
      })
      .catch(() => {});
  }, []);

  // ── 최초 인사 TTS (1회) ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!hasGreeted) {
      hasGreeted = true;
      setTtsReady(true);
    }
  }, [firstEvent]);

  useEffect(() => {
    if (ttsReady) setIdleAutoPlay(true);
  }, [ttsReady]);

  // ── 화면 재진입 시 idle 메시지 재생 ──────────────────────────────────────
  useFocusEffect(
    useCallback(() => {
      if (hasGreeted) setIdleAutoPlay(true);
    }, [])
  );

  // ── TTS 메시지 ──────────────────────────────────────────────────────────────
  const greetingMessage = firstEvent
    ? `우리 톡 뱅킹입니다.\n현재 진행 중인 이벤트는\n${firstEvent.title} 입니다.`
    : '우리 톡 뱅킹입니다.';

  const ttsContent =
    voiceState === 'listening' ? { message: '말씀해 주세요',         autoPlay: true } :
    voiceState === 'error'     ? { message: '다시 말씀해 주세요.',    autoPlay: true } :
    ttsReady && !idleAutoPlay  ? { message: greetingMessage,         autoPlay: true } :
                                 { message: '어떤 업무를\n도와드릴까요?', autoPlay: idleAutoPlay };

  // ── 퀵 메뉴 ──────────────────────────────────────────────────────────────
  const menuItems: VoiceQuickMenuItem[] = HOME_MENU_ITEMS.map((item) => {
    const pressMap: Record<string, (() => void) | undefined> = {
      '이벤트':   onEventMenuPress,
      '이체하기': onTransferPress,
      '내 자산':  onAssetPress,
      '자동이체': onAutoTransferPress,
    };
    return { ...item, onPress: pressMap[item.label] ?? (() => {}) };
  });

  return (
    <View style={styles.root}>

      {/* 상단 */}
      <View style={styles.body}>
        <TopBar variant="logo" />

        <TtsBubble
          message={ttsContent.message}
          variant={voiceState === 'error' ? 'error' : 'default'}
          autoPlay={ttsContent.autoPlay}
          onEnd={() => {
            if (ttsReady && !idleAutoPlay) {
              setTtsReady(false);
              setIdleAutoPlay(true);
            } else {
              setIdleAutoPlay(false);
            }
          }}
        />

        {/* 이벤트 배너 */}
        {firstEvent && (
          <EventBanner
            event={firstEvent}
            onPress={() => onEventBannerPress(firstEvent.event_id)}
          />
        )}

        {/* 마이크 버튼 (SCR-003 중앙) */}
        <View style={styles.micArea}>
          <HomeVoiceSection
            micState={voiceState}
            primaryHint={voiceState === 'idle' ? '말씀해 주세요' : undefined}
            subCaption={voiceState === 'idle' ? '화면 꾹 누르기로 활성화' : undefined}
            onMicPress={activateMic}
            onMicRelease={stopMic}
          />
        </View>

        {/* 퀵 메뉴 */}
        <VoiceQuickMenuGrid items={menuItems} />
      </View>

      {/* 탭 바 */}
      <TabBar activeTab="home" onTabChange={() => {}} />

    </View>
  );
}

// ── 스타일 ────────────────────────────────────────────────────────────────────

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
  micArea: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
