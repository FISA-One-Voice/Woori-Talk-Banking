// =============================================================================
// frontend/store/eventStore.ts
//
// [역할]
// 이벤트 참여 상태를 전역으로 관리하는 Zustand 스토어.
// API 호출 시 authStore 에서 토큰을 꺼내 Authorization 헤더에 첨부합니다.
//
// [상태]
// joinedIds  - 참여 완료된 이벤트 ID 목록 (앱 실행 중 유지)
// joinStatus - 현재 참여 요청 진행 상태
//
// [joinStatus 흐름]
// idle → (참여하기 확인) → loading → success / duplicate / error
//                                          ↓
//                                    resetJoinStatus() → idle
// =============================================================================

import { create } from 'zustand';
import { apiClient } from '@/utils/api';

export type JoinStatus = 'idle' | 'loading' | 'success' | 'duplicate' | 'error';

interface EventState {
  /** 참여 완료된 이벤트 ID 목록 */
  joinedIds: string[];

  /** 현재 참여 요청 상태 */
  joinStatus: JoinStatus;

  /**
   * 이벤트 참여 요청.
   * authStore 의 토큰을 자동으로 헤더에 첨부합니다.
   */
  joinEvent: (eventId: string) => Promise<void>;

  /**
   * joinStatus 를 idle 로 초기화.
   * 모달이 닫힐 때 호출하세요.
   */
  resetJoinStatus: () => void;
}

export const useEventStore = create<EventState>((set, get) => ({
  joinedIds: [],
  joinStatus: 'idle',

  joinEvent: async (eventId: string) => {
    set({ joinStatus: 'loading' });

    try {
      // 인터셉터가 authStore 토큰을 자동으로 헤더에 첨부합니다.
      await apiClient.post(`/api/events/${eventId}/join`, {});

      set((state) => ({
        joinStatus: 'success',
        joinedIds: [...state.joinedIds, eventId],
      }));
    } catch (err: unknown) {
      const code = (err as { response?: { data?: { code?: string } } })
        ?.response?.data?.code;

      if (code === 'ALREADY_PARTICIPATED') {
        // 이미 참여한 경우 → joinedIds 에 추가 후 중복 상태
        set((state) => ({
          joinStatus: 'duplicate',
          joinedIds: state.joinedIds.includes(eventId)
            ? state.joinedIds
            : [...state.joinedIds, eventId],
        }));
      } else {
        set({ joinStatus: 'error' });
      }
    }
  },

  resetJoinStatus: () => set({ joinStatus: 'idle' }),
}));
