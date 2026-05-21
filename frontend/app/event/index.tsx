// =============================================================================
// frontend/app/event/index.tsx
//
// [이 파일의 역할]
// SCR-007 F01 — 이벤트 목록 화면입니다.
// 서버에서 이벤트 목록을 불러와 카드 형태로 보여줍니다.
// 카드를 누르거나 음성으로 번호를 말하면 상세 화면으로 이동합니다.
//
// [Expo Router 파일 라우팅]
// 이 파일의 위치: app/event/index.tsx
// 이 파일에 해당하는 URL: /event
// 즉, router.push('/event') 하면 이 화면이 열립니다.
//
// [화면 흐름]
// 1. 화면이 열리면 자동으로 이벤트 목록을 불러옵니다. (useEffect)
// 2. 불러오는 동안 로딩 스피너를 표시합니다.
// 3. 이벤트가 있으면 카드 목록을 표시합니다.
// 4. 이벤트가 없으면 EmptyState 를 표시합니다.
// 5. 하단 VoiceInputBar 버튼을 누르면 음성 입력 상태가 바뀝니다.
// =============================================================================

import { useRouter } from 'expo-router'; // 화면 이동(네비게이션)을 담당하는 훅
import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import EmptyState from '@/components/EmptyState';
import EventCard from '@/components/EventCard';
import VoiceInputBar, { VoiceStatus } from '@/components/VoiceInputBar';
import { useEventStore } from '@/store/eventStore';

// 날짜 문자열(ISO 8601)을 한국어 형식으로 변환하는 함수
// 예: "2024-01-01T00:00:00Z" → "2024년 1월 1일"
function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

export default function EventListScreen() {
  const router = useRouter(); // 화면 이동 함수들을 제공하는 객체

  // 스토어에서 필요한 데이터와 함수를 가져옵니다.
  // 구조 분해 할당: 스토어 객체에서 필요한 것만 꺼내 씁니다.
  const { events, isLoading, fetchEvents } = useEventStore();

  // 음성 입력 상태를 이 화면에서 직접 관리합니다.
  // useState: 화면 내부에서만 사용하는 상태를 만드는 함수
  // 초기값은 'idle' (대기 상태)
  const [voiceStatus, setVoiceStatus] = useState<VoiceStatus>('idle');

  // useEffect: 화면이 처음 열릴 때 딱 한 번 실행됩니다.
  // 빈 배열([])을 두 번째 인자로 넘기면 "화면 마운트 시 한 번만 실행"이라는 의미입니다.
  useEffect(() => {
    fetchEvents(); // 서버에서 이벤트 목록을 불러옵니다.
  }, [fetchEvents]);

  // 마이크 버튼을 눌렀을 때 실행되는 함수
  const handleMicPress = () => {
    if (voiceStatus === 'idle') {
      setVoiceStatus('recording'); // 녹음 시작
      // TODO: 실제 STT(음성→텍스트) 녹음 시작 코드를 여기에 추가합니다.
      // 지금은 3초 후 자동으로 idle 로 돌아가는 임시 코드입니다.
      setTimeout(() => setVoiceStatus('idle'), 3000);
    } else if (voiceStatus === 'recording') {
      setVoiceStatus('idle'); // 녹음 중단
    }
  };

  // 이벤트 카드를 눌렀을 때 상세 화면으로 이동합니다.
  // eventId: 누른 카드의 이벤트 UUID
  const handleCardPress = (eventId: string) => {
    // Expo Router 동적 라우팅: /event/{uuid} 형태로 이동
    router.push(`/event/${eventId}`);
  };

  return (
    // SafeAreaView: 노치(카메라 구멍)나 홈 인디케이터와 겹치지 않게 안전 영역을 잡아줍니다.
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.container}>
        {/* 화면 제목 */}
        <Text style={styles.heading}>이벤트</Text>

        {/* 로딩 중일 때 스피너를 표시합니다 */}
        {isLoading ? (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color={COLORS.highlightYellow} />
            <Text style={styles.loadingText}>이벤트를 불러오는 중...</Text>
          </View>
        ) : (
          // ScrollView: 내용이 화면보다 길면 스크롤할 수 있게 해줍니다.
          <ScrollView
            style={styles.list}
            // VoiceInputBar 가 하단에 고정되므로 그 높이만큼 여백을 줍니다.
            contentContainerStyle={styles.listContent}
          >
            {events.length === 0 ? (
              // 이벤트가 없을 때 EmptyState 컴포넌트를 표시합니다.
              <EmptyState
                message="현재 진행 중인 이벤트가 없습니다."
                icon="📋"
              />
            ) : (
              // events 배열의 각 항목을 EventCard 컴포넌트로 변환합니다.
              // map: 배열의 각 요소를 다른 형태로 변환하는 JavaScript 배열 함수
              events.map((event) => (
                // key: React 가 목록 항목을 구별하기 위해 반드시 필요한 고유값
                <EventCard
                  key={event.event_id}
                  title={event.title}
                  // 시작일 ~ 종료일 형식으로 날짜 문자열을 만듭니다.
                  date={`${formatDate(event.start_at)} ~ ${formatDate(event.end_at)}`}
                  onPress={() => handleCardPress(event.event_id)}
                />
              ))
            )}
          </ScrollView>
        )}
      </View>

      {/* 화면 하단에 고정되는 음성 입력 버튼 */}
      <VoiceInputBar
        status={voiceStatus}
        onPress={handleMicPress}
        // 이벤트를 불러오는 중에는 마이크 버튼을 비활성화합니다.
        disabled={isLoading}
      />
    </SafeAreaView>
  );
}

// ── 스타일 ─────────────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  container: {
    flex: 1,
    padding: LAYOUT.paddingMedium,
  },
  heading: {
    fontSize: FONT_SIZES.body,
    fontWeight: '700',
    color: COLORS.textMain,
    marginBottom: 16,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 12,
  },
  loadingText: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
  },
  list: {
    flex: 1,
  },
  listContent: {
    // VoiceInputBar 높이(약 140px)만큼 하단 여백을 줍니다.
    // 이 여백이 없으면 마지막 카드가 VoiceInputBar 에 가려집니다.
    paddingBottom: 140,
  },
});
