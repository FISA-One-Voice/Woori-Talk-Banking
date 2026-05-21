// =============================================================================
// frontend/app/event/[id].tsx
//
// [이 파일의 역할]
// SCR-007 F02/F03 — 이벤트 상세 화면 + 참여 처리 화면입니다.
// 선택한 이벤트의 상세 정보를 보여주고, 참여 버튼을 통해 이벤트에 참여합니다.
//
// [Expo Router 동적 라우팅]
// 파일 이름의 [id] 부분이 URL 의 숫자로 바뀝니다.
// 예: /event/3 → id = "3"  (문자열로 옵니다. 숫자로 변환해서 사용해야 합니다.)
//
// [화면 흐름]
// 1. URL 에서 id 를 꺼냅니다. (useLocalSearchParams)
// 2. 화면이 열리면 이벤트 상세 정보를 불러옵니다. (useEffect)
// 3. 로딩 중에는 ActivityIndicator 를 표시합니다.
// 4. 불러오기 완료 후 이벤트 제목/설명/날짜/참여자 수를 표시합니다.
// 5. '참여하기' 버튼을 누르면 백엔드 POST API 를 호출합니다.
//    - 성공 → SuccessScreen 으로 전환 (확인 버튼 누르면 목록으로 돌아감)
//    - 오류 → ErrorModal 팝업 표시
// 6. 오류 종류 매핑:
//    - 'ALREADY_PARTICIPATED' → ErrorModal type='already'
//    - 'NETWORK_ERROR'        → ErrorModal type='network'
//    - 그 외                  → ErrorModal type='server'
// =============================================================================

import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import ErrorModal from '@/components/ErrorModal';
import SuccessScreen from '@/components/SuccessScreen';
import VoiceInputBar, { VoiceStatus } from '@/components/VoiceInputBar';
import { useEventStore } from '@/store/eventStore';

// ErrorModal 이 받을 수 있는 오류 종류 (ErrorModal.tsx 에 정의된 것과 동일)
type ErrorType = 'already' | 'server' | 'network';

// 백엔드 error_code → ErrorModal type 변환 함수
// 백엔드가 보내는 문자열 코드를 프론트엔드 ErrorModal 이 이해하는 타입으로 바꿉니다.
function toErrorType(errorCode: string | undefined): ErrorType {
  if (errorCode === 'ALREADY_PARTICIPATED') return 'already';
  if (errorCode === 'NETWORK_ERROR') return 'network';
  return 'server'; // EVENT_NOT_FOUND, EVENT_ENDED, 그 외 모든 코드
}

// 날짜 문자열(ISO 8601)을 한국어 형식으로 변환하는 함수
// 예: "2024-01-01T00:00:00Z" → "2024년 1월 1일"
function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

export default function EventDetailScreen() {
  const router = useRouter();

  // useLocalSearchParams: URL 에서 경로 파라미터를 꺼냅니다.
  // /event/3 으로 접근하면 params.id = "3" (문자열)
  const { id } = useLocalSearchParams<{ id: string }>();

  // 스토어에서 상세 이벤트 데이터와 로딩 상태, API 함수를 가져옵니다.
  const { selectedEvent, isLoading, fetchEventDetail, participate } = useEventStore();

  // 음성 입력 상태 (이 화면에서만 사용하는 로컬 상태)
  const [voiceStatus, setVoiceStatus] = useState<VoiceStatus>('idle');

  // 참여 성공 여부 (true 이면 SuccessScreen 으로 전환됩니다)
  const [isSuccess, setIsSuccess] = useState(false);

  // 오류 모달 표시 여부 (null 이면 닫힘, 값이 있으면 해당 타입으로 열림)
  const [errorType, setErrorType] = useState<ErrorType | null>(null);

  // 참여 버튼 자체의 로딩 상태 (중복 클릭 방지용)
  const [isParticipating, setIsParticipating] = useState(false);

  // useEffect: 화면이 처음 열릴 때 이벤트 상세 정보를 불러옵니다.
  // id 가 바뀔 때도 다시 불러옵니다. (뒤로가기 후 다른 이벤트 클릭 시)
  useEffect(() => {
    if (id) {
      // id 는 URL 경로 파라미터로 온 UUID 문자열입니다. 변환 없이 그대로 사용합니다.
      fetchEventDetail(id);
    }
  }, [id, fetchEventDetail]);

  // 마이크 버튼 처리 (3초 후 자동 idle 복귀 — STT 연결 전 임시 코드)
  const handleMicPress = () => {
    if (voiceStatus === 'idle') {
      setVoiceStatus('recording');
      // TODO: 실제 STT 녹음 시작 코드로 교체합니다.
      setTimeout(() => setVoiceStatus('idle'), 3000);
    } else if (voiceStatus === 'recording') {
      setVoiceStatus('idle');
    }
  };

  // '참여하기' 버튼을 눌렀을 때 실행됩니다.
  const handleParticipate = async () => {
    // 이미 참여 요청 중이거나 이벤트 데이터가 없으면 실행하지 않습니다.
    if (isParticipating || !selectedEvent) return;

    setIsParticipating(true); // 버튼 비활성화 시작

    // 스토어의 participate 함수를 호출합니다.
    // 결과는 { success: boolean, errorCode?: string } 형태입니다.
    const result = await participate(selectedEvent.event_id);

    setIsParticipating(false); // 버튼 비활성화 해제

    if (result.success) {
      setIsSuccess(true); // SuccessScreen 으로 전환
    } else {
      // error_code 를 ErrorModal 타입으로 변환해서 모달을 엽니다.
      setErrorType(toErrorType(result.errorCode));
    }
  };

  // ── 조건부 렌더링 ────────────────────────────────────────────────────────────

  // 참여 성공 → SuccessScreen 으로 전체 화면 전환
  // if 문으로 return 을 일찍 하면 이후 코드가 실행되지 않습니다.
  if (isSuccess && selectedEvent) {
    return (
      <SuccessScreen
        eventName={selectedEvent.title}
        onConfirm={() => router.back()} // '확인' 누르면 이벤트 목록으로 돌아갑니다.
      />
    );
  }

  // 이벤트 데이터를 불러오는 중
  if (isLoading && !selectedEvent) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={COLORS.highlightYellow} />
          <Text style={styles.loadingText}>이벤트를 불러오는 중...</Text>
        </View>
      </SafeAreaView>
    );
  }

  // 데이터를 불러왔지만 이벤트가 없는 경우 (잘못된 id 접근 등)
  if (!selectedEvent) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.loadingContainer}>
          <Text style={styles.errorText}>이벤트를 찾을 수 없습니다.</Text>
          <Pressable style={styles.backButton} onPress={() => router.back()}>
            <Text style={styles.backButtonText}>돌아가기</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  // ── 정상 화면 렌더링 ─────────────────────────────────────────────────────────
  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.container}>
        {/* 화면 제목 */}
        <Text style={styles.heading}>이벤트 상세</Text>

        {/* 이벤트 내용 스크롤 영역 */}
        <ScrollView
          style={styles.scroll}
          contentContainerStyle={styles.scrollContent}
        >
          {/* 이벤트 제목 카드 */}
          <View style={styles.card}>
            <Text style={styles.eventTitle}>{selectedEvent.title}</Text>
          </View>

          {/* 이벤트 정보 카드 (날짜 / 참여자 수) */}
          <View style={styles.card}>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>기간</Text>
              <Text style={styles.infoValue}>
                {formatDate(selectedEvent.start_at)}
                {' ~ '}
                {formatDate(selectedEvent.end_at)}
              </Text>
            </View>

            <View style={[styles.infoRow, styles.infoRowLast]}>
              <Text style={styles.infoLabel}>참여자</Text>
              <Text style={styles.infoValue}>
                {selectedEvent.participant_count.toLocaleString()}명
              </Text>
            </View>
          </View>

          {/* 이벤트 설명 카드 */}
          <View style={styles.card}>
            <Text style={styles.descriptionLabel}>이벤트 내용</Text>
            <Text style={styles.description}>{selectedEvent.description}</Text>
          </View>

          {/* 참여하기 버튼 */}
          <Pressable
            style={({ pressed }) => [
              styles.participateButton,
              // 로딩 중이거나 누르는 중이면 시각적으로 비활성화 표시
              (isParticipating || isLoading) && styles.participateButtonDisabled,
              pressed && styles.participateButtonPressed,
            ]}
            onPress={handleParticipate}
            // 중복 클릭 방지: 이미 요청 중이면 버튼을 비활성화합니다.
            disabled={isParticipating || isLoading}
          >
            {isParticipating ? (
              // 참여 요청 중에는 스피너를 표시합니다.
              <ActivityIndicator color={COLORS.background} />
            ) : (
              <Text style={styles.participateButtonText}>참여하기</Text>
            )}
          </Pressable>
        </ScrollView>
      </View>

      {/* 하단 고정 음성 입력 버튼 */}
      <VoiceInputBar
        status={voiceStatus}
        onPress={handleMicPress}
        disabled={isLoading || isParticipating}
      />

      {/* 오류 팝업: errorType 이 null 이 아닐 때만 표시됩니다. */}
      <ErrorModal
        visible={errorType !== null}
        type={errorType ?? 'server'} // null 일 수 없지만 TypeScript 만족을 위해 기본값 지정
        onClose={() => setErrorType(null)} // '확인' 누르면 모달을 닫습니다.
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
  scroll: {
    flex: 1,
  },
  scrollContent: {
    // VoiceInputBar 높이(약 140px)만큼 하단 여백을 줍니다.
    paddingBottom: 140,
    gap: 12, // 카드 사이 간격
  },
  card: {
    backgroundColor: COLORS.surface,
    borderRadius: LAYOUT.cardRadius,
    borderWidth: 1,
    borderColor: COLORS.border,
    padding: LAYOUT.cardPadding,
  },
  eventTitle: {
    fontSize: FONT_SIZES.body,
    fontWeight: '700',
    color: COLORS.textMain,
    lineHeight: 32,
  },
  infoRow: {
    flexDirection: 'row', // 라벨과 값을 가로로 배치합니다.
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  infoRowLast: {
    borderBottomWidth: 0, // 마지막 행은 하단 구분선을 없앱니다.
  },
  infoLabel: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
    fontWeight: '600',
  },
  infoValue: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.textMain,
    flex: 1,
    textAlign: 'right',
  },
  descriptionLabel: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
    fontWeight: '600',
    marginBottom: 8,
  },
  description: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.textMain,
    lineHeight: 28,
  },
  participateButton: {
    backgroundColor: COLORS.highlightYellow,
    paddingVertical: 16,
    borderRadius: LAYOUT.borderRadius,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 56,
  },
  participateButtonDisabled: {
    opacity: 0.5,
  },
  participateButtonPressed: {
    opacity: 0.8,
  },
  participateButtonText: {
    fontSize: FONT_SIZES.button,
    fontWeight: '700',
    color: COLORS.background,
  },
  // 로딩/오류 상태에서 중앙 정렬을 위한 컨테이너
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 16,
  },
  loadingText: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
  },
  errorText: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
  },
  backButton: {
    backgroundColor: COLORS.surface,
    paddingVertical: 12,
    paddingHorizontal: 32,
    borderRadius: LAYOUT.borderRadius,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  backButtonText: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.textMain,
    fontWeight: '600',
  },
});
