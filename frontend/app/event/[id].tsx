// =============================================================================
// app/event/[id].tsx   (SCR-007 이벤트 상세)
//
// [화면 흐름]
// loading    → 데이터 로딩 중
// detail     → 이벤트 상세 + "목록" / "참여하기" 버튼
// not_found  → 이벤트 없음
//
// [참여 확인 모달 상태]
// confirm    → 이벤트 정보 확인 + 참여 동의 (로컬 UI 상태)
// processing → 처리 중, loading 상태와 동기화 (버튼 비활성)
// success    → 참여 완료 → 홈으로 이동
// duplicate  → 이미 참여
// error      → 오류
//
// [Zustand 스토어]
// useEventStore → 참여 요청 + 참여 완료 ID 목록 관리 (토큰은 api.ts 인터셉터가 자동 첨부)
// =============================================================================

import { ActionButton } from '@/components/display';
import { TtsBubble } from '@/components/feedback';
import { TopBar } from '@/components/layout';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import { apiClient, type ApiResponse } from '@/utils/api';
import { useScreenAnnounce } from '@/hooks/useScreenAnnounce';
import { useMic } from '@/context/MicContext';
import { useEventStore } from '@/store/eventStore';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Modal,
  Platform,
  StatusBar,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';

// ── 타입 ─────────────────────────────────────────────────────────────────────

interface EventDetail {
  event_id: string;
  title: string;
  description: string | null;
  banner_image_url: string | null;
  is_active: boolean;
  start_at: string;
  end_at: string;
}

type Screen     = 'loading' | 'detail' | 'not_found';
type ModalState = 'confirm' | 'processing' | 'success' | 'duplicate' | 'error' | null;

// ── 헬퍼 ─────────────────────────────────────────────────────────────────────

function formatEndDate(dateStr: string): string {
  const d = new Date(dateStr);
  return `~${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`;
}

// ── 이벤트 정보 카드 ──────────────────────────────────────────────────────────

function EventDetailCard({ event }: { event: EventDetail }) {
  return (
    <View style={cardStyles.container}>
      <View style={cardStyles.row}>
        <Text style={cardStyles.label}>이벤트</Text>
        <Text style={cardStyles.value}>{event.title}</Text>
      </View>
      <View style={cardStyles.divider} />
      <View style={cardStyles.row}>
        <Text style={cardStyles.label}>혜택</Text>
        <Text style={[cardStyles.value, cardStyles.highlight]}>
          {event.description ?? '-'}
        </Text>
      </View>
      <View style={cardStyles.divider} />
      <View style={cardStyles.row}>
        <Text style={cardStyles.label}>기간</Text>
        <Text style={cardStyles.value}>{formatEndDate(event.end_at)}</Text>
      </View>
    </View>
  );
}

const cardStyles = StyleSheet.create({
  container: {
    backgroundColor: COLORS.surface,
    borderWidth: 0.5,
    borderColor: COLORS.border,
    borderRadius: LAYOUT.borderRadius,
    paddingVertical: 8,
    paddingHorizontal: 16,
    marginBottom: 16,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 14,
  },
  divider: { height: 0.5, backgroundColor: COLORS.border },
  label: {
    fontSize: FONT_SIZES.body,
    color: COLORS.grayMedium,
  },
  value: {
    fontSize: FONT_SIZES.body,
    color: COLORS.textMain,
    fontWeight: '500',
    flexShrink: 1,
    textAlign: 'right',
    marginLeft: 12,
  },
  highlight: { color: COLORS.highlightYellow },
});

// ── 참여 확인 모달 ────────────────────────────────────────────────────────────

interface ParticipateModalProps {
  event: EventDetail;
  modalState: ModalState;
  onConfirm: () => void;
  onClose: () => void;
}

function ParticipateModal({
  event,
  modalState,
  onConfirm,
  onClose,
}: ParticipateModalProps) {
  const { activateMic } = useMic();
  if (!modalState) return null;

  const isConfirm    = modalState === 'confirm' || modalState === 'processing';
  const isProcessing = modalState === 'processing';
  const isSuccess    = modalState === 'success';
  const isDuplicate  = modalState === 'duplicate';
  const isError      = modalState === 'error';
  const isDone       = isSuccess || isDuplicate || isError;

  const ttsMessage =
    isConfirm   ? `${event.title}\n참여하시겠어요?`    :
    isSuccess   ? '이벤트 참여가 완료되었습니다!'       :
    isDuplicate ? '이미 참여하신 이벤트입니다.'         :
                  '참여 처리 중 오류가 발생했습니다.';

  return (
    <Modal transparent animationType="fade" visible onRequestClose={onClose}>
      <View style={modalStyles.overlay}>
        <View style={modalStyles.card}>

          <TtsBubble
            message={ttsMessage}
            variant={isError ? 'error' : 'default'}
            autoPlay
          />

          {isConfirm && <EventDetailCard event={event} />}

          {isDone && (
            <View style={modalStyles.resultRow}>
              <Text style={modalStyles.resultIcon}>
                {isSuccess ? '✅' : isDuplicate ? 'ℹ️' : '⚠️'}
              </Text>
              <Text style={[
                modalStyles.resultText,
                isError && { color: COLORS.error },
              ]}>
                {isSuccess   ? '참여가 완료되었습니다!'    :
                 isDuplicate ? '이미 참여하신 이벤트입니다.' :
                               '처리 중 오류가 발생했습니다.'}
              </Text>
            </View>
          )}

          <View style={modalStyles.buttonRow}>
            {isConfirm && (
              <>
                <TouchableOpacity
                  style={[modalStyles.btn, modalStyles.btnOutline]}
                  onPress={onClose}
                  onLongPress={activateMic}
                  delayLongPress={600}
                  disabled={isProcessing}
                  activeOpacity={0.7}
                >
                  <Text style={modalStyles.btnTextOutline}>취소</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[
                    modalStyles.btn,
                    modalStyles.btnPrimary,
                    isProcessing && modalStyles.btnDisabled,
                  ]}
                  onPress={onConfirm}
                  onLongPress={activateMic}
                  delayLongPress={600}
                  disabled={isProcessing}
                  activeOpacity={0.7}
                >
                  <Text style={modalStyles.btnTextPrimary}>
                    {isProcessing ? '처리 중...' : '참여하기'}
                  </Text>
                </TouchableOpacity>
              </>
            )}

            {isDone && (
              <TouchableOpacity
                style={[modalStyles.btn, modalStyles.btnPrimary, { flex: 1 }]}
                onPress={onClose}
                onLongPress={activateMic}
                delayLongPress={600}
                activeOpacity={0.7}
              >
                <Text style={modalStyles.btnTextPrimary}>
                  {isSuccess ? '확인' : '닫기'}
                </Text>
              </TouchableOpacity>
            )}
          </View>

        </View>
      </View>
    </Modal>
  );
}

const modalStyles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.65)',
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 20,
  },
  card: {
    width: '100%',
    backgroundColor: COLORS.surface,
    borderRadius: LAYOUT.borderRadius + 4,
    padding: 20,
    gap: 12,
  },
  resultRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 8,
  },
  resultIcon: { fontSize: 28 },
  resultText: {
    fontSize: FONT_SIZES.body,
    color: COLORS.textMain,
    fontWeight: '600',
    flex: 1,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 4,
  },
  btn: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: LAYOUT.borderRadius,
    alignItems: 'center',
  },
  btnOutline: {
    borderWidth: 1,
    borderColor: COLORS.grayDeep,
  },
  btnPrimary: {
    backgroundColor: COLORS.highlightYellow,
  },
  btnDisabled: { opacity: 0.5 },
  btnTextOutline: {
    fontSize: FONT_SIZES.body,
    color: '#111111',
    fontWeight: '600',
  },
  btnTextPrimary: {
    fontSize: FONT_SIZES.body,
    color: '#111111',
    fontWeight: '700',
  },
});

// ── 메인 화면 ─────────────────────────────────────────────────────────────────

export default function EventDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [screen, setScreen] = useState<Screen>('loading');
  const [event, setEvent] = useState<EventDetail | null>(null);
  const [modalState, setModalState] = useState<ModalState>(null);

  // Zustand 스토어
  const { joinedIds, joinStatus, joinEvent, resetJoinStatus } = useEventStore();

  // DB 기준 참여 여부 (이벤트 로딩 시 백엔드에서 받아옴)
  const [dbParticipated, setDbParticipated] = useState(false);

  // DB 참여 여부 OR 이번 세션에서 참여한 경우 모두 반영
  const participated =
    dbParticipated || (event ? joinedIds.includes(event.event_id) : false);

  useScreenAnnounce('이벤트 상세 화면입니다.');

  // joinStatus 변화 → modalState 동기화
  useEffect(() => {
    if (joinStatus === 'loading')   setModalState('processing');
    else if (joinStatus === 'success')   setModalState('success');
    else if (joinStatus === 'duplicate') setModalState('duplicate');
    else if (joinStatus === 'error')     setModalState('error');
  }, [joinStatus]);

  useEffect(() => {
    fetchEventDetail();
  }, [id]);

  async function fetchEventDetail(): Promise<void> {
    try {
      // 인터셉터가 authStore 토큰을 자동으로 헤더에 첨부합니다.
      const res = await apiClient.get<ApiResponse<EventDetail & { has_participated: boolean }>>(
        `/api/events/${id}`,
      );
      if (res.data.success && res.data.data) {
        setEvent(res.data.data);
        setDbParticipated(res.data.data.has_participated ?? false);
        setScreen('detail');
      } else {
        setScreen('not_found');
      }
    } catch {
      setScreen('not_found');
    }
  }

  function handleConfirmParticipate(): void {
    if (!event) return;
    joinEvent(event.event_id);  // 인터셉터가 authStore 토큰을 자동으로 첨부합니다.
  }

  function handleCloseModal(): void {
    setModalState(null);
    resetJoinStatus();
  }

  const ttsMap: Record<Screen, { message: string; variant: 'default' | 'error' }> = {
    loading:   { message: '이벤트 정보를 불러오고 있습니다.', variant: 'default' },
    detail:    { message: `${event?.title ?? ''}\n참여하시겠어요?`,  variant: 'default' },
    not_found: { message: '이벤트를 찾을 수\n없습니다.',            variant: 'error'   },
  };
  const tts = ttsMap[screen];

  return (
    <View style={styles.root}>
      {event && modalState && (
        <ParticipateModal
          event={event}
          modalState={modalState}
          onConfirm={handleConfirmParticipate}
          onClose={handleCloseModal}
        />
      )}

      <View style={styles.body}>
        <TopBar variant="back" title="이벤트" onBack={() => router.back()} />
        <TtsBubble message={tts.message} variant={tts.variant} autoPlay={screen !== 'loading'} />

        {screen === 'loading' && (
          <View style={styles.center}>
            <ActivityIndicator size="large" color={COLORS.highlightYellow} />
          </View>
        )}

        {screen === 'detail' && event && (
          <>
            <EventDetailCard event={event} />
            <View style={styles.bottom}>
              <View style={styles.buttonRow}>
                <ActionButton
                  label="목록"
                  variant="outline"
                  flex={1}
                  onPress={() => router.push('/event' as never)}
                />
                <ActionButton
                  label={participated ? '참여완료' : '참여하기'}
                  variant={participated ? 'outline' : 'primary'}
                  flex={2}
                  disabled={participated}
                  onPress={() => setModalState('confirm')}
                />
              </View>
            </View>
          </>
        )}

        {screen === 'not_found' && (
          <View style={styles.bottom}>
            <ActionButton
              label="목록으로 돌아가기"
              variant="outline"
              onPress={() => router.back()}
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
  bottom: {
    flex: 1,
    justifyContent: 'flex-end',
    paddingBottom: 32,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: 10,
  },
});
