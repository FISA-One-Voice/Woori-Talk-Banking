// =============================================================================
// frontend/store/eventStore.ts
//
// [이 파일의 역할]
// 이벤트 화면에서 필요한 데이터와 상태를 전역으로 관리합니다.
// Zustand 를 사용해서 이벤트 목록, 선택한 이벤트, 로딩 여부 등을 저장합니다.
//
// [왜 스토어가 필요한가?]
// React 에서 화면(컴포넌트)이 바뀌면 그 안의 변수는 사라집니다.
// 이벤트 목록 화면에서 불러온 데이터를 상세 화면에서도 쓰려면
// 화면 밖 어딘가에 저장해야 합니다. 그것이 스토어입니다.
//
// [다른 파일과의 관계]
// ├─ services/eventService.ts → API 호출 함수를 사용합니다.
// ├─ app/event/index.tsx      → events, fetchEvents 를 사용합니다.
// └─ app/event/[id].tsx       → selectedEvent, fetchEventDetail, participate 를 사용합니다.
//
// [Zustand 사용법]
// import { useEventStore } from '../store/eventStore';
// const { events, fetchEvents } = useEventStore();  // 필요한 것만 꺼내 씁니다.
// =============================================================================

import { create } from "zustand"; // Zustand 스토어 생성 함수

import { eventService } from "../services/eventService";
import type { Event, EventDetail } from "../types/event";

// 스토어에 들어갈 데이터와 함수의 형태를 정의합니다.
interface EventStore {
  // ── 데이터 (상태) ────────────────────────────────────────────────────────────
  events: Event[]; // 이벤트 목록
  selectedEvent: EventDetail | null; // 현재 선택된 이벤트 상세 (없으면 null)
  isLoading: boolean; // API 호출 중이면 true → 화면에 로딩 스피너 표시
  errorCode: string | null; // 오류 코드 (없으면 null)

  // ── 함수 (액션) ────────────────────────────────────────────────────────────
  fetchEvents: () => Promise<void>;
  fetchEventDetail: (eventId: string) => Promise<void>;
  participate: (eventId: string) => Promise<{ success: boolean; errorCode?: string }>;
  clearError: () => void; // 오류 상태를 초기화합니다.
}

// create() 로 스토어를 생성합니다.
// set 함수로 상태를 변경합니다. set({ key: value }) 형태로 사용합니다.
export const useEventStore = create<EventStore>((set) => ({
  // ── 초기값 ──────────────────────────────────────────────────────────────────
  events: [],
  selectedEvent: null,
  isLoading: false,
  errorCode: null,

  // ── 이벤트 목록 불러오기 ─────────────────────────────────────────────────────
  fetchEvents: async () => {
    set({ isLoading: true, errorCode: null }); // 로딩 시작

    try {
      const response = await eventService.getEvents();

      if (response.success && response.data) {
        set({ events: response.data }); // 성공: 데이터 저장
      } else {
        // API 는 성공(200)으로 응답했지만 success: false 인 경우
        set({ errorCode: response.error_code ?? "UNKNOWN_ERROR" });
      }
    } catch {
      // 네트워크 오류, 서버 다운 등 예외 상황
      set({ errorCode: "NETWORK_ERROR" });
    } finally {
      // finally: 성공하든 실패하든 반드시 실행됩니다.
      set({ isLoading: false }); // 로딩 종료
    }
  },

  // ── 이벤트 상세 불러오기 ─────────────────────────────────────────────────────
  fetchEventDetail: async (eventId: string) => {
    set({ isLoading: true, errorCode: null, selectedEvent: null });

    try {
      const response = await eventService.getEventDetail(eventId);

      if (response.success && response.data) {
        set({ selectedEvent: response.data });
      } else {
        set({ errorCode: response.error_code ?? "UNKNOWN_ERROR" });
      }
    } catch {
      set({ errorCode: "NETWORK_ERROR" });
    } finally {
      set({ isLoading: false });
    }
  },

  // ── 이벤트 참여 ─────────────────────────────────────────────────────────────
  // 참여 함수는 성공/실패 여부를 반환해서 화면에서 결과를 처리합니다.
  participate: async (eventId: string) => {
    set({ isLoading: true });

    try {
      const response = await eventService.participate(eventId);
      set({ isLoading: false });

      // 성공/실패 여부와 오류 코드를 반환합니다.
      // 화면([id].tsx)에서 이 결과를 받아 SuccessScreen 또는 ErrorModal 을 표시합니다.
      return {
        success: response.success,
        errorCode: response.error_code,
      };
    } catch {
      set({ isLoading: false });
      return { success: false, errorCode: "NETWORK_ERROR" };
    }
  },

  // ── 오류 초기화 ─────────────────────────────────────────────────────────────
  clearError: () => set({ errorCode: null }),
}));
