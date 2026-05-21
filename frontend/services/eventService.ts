// =============================================================================
// frontend/services/eventService.ts
//
// [이 파일의 역할]
// 백엔드 API 를 호출하는 함수들을 모아놓은 파일입니다.
// 화면이나 스토어에서 axios 를 직접 사용하지 않고,
// 반드시 이 파일의 함수를 통해서만 API 를 호출합니다.
//
// [이렇게 하는 이유]
// 나중에 API 주소나 요청 방식이 바뀌어도 이 파일만 수정하면 됩니다.
// 화면 파일들은 수정할 필요가 없습니다.
//
// [다른 파일과의 관계]
// └─ store/eventStore.ts → 이 파일의 함수를 호출합니다.
// =============================================================================

import axios from "axios"; // HTTP 요청 라이브러리 (fetch 보다 사용하기 편합니다)

import type {
  ApiResponse,
  Event,
  EventDetail,
  ParticipationResult,
} from "../types/event";

// 백엔드 서버 주소
// 개발 중: 내 컴퓨터에서 uvicorn 으로 실행한 서버
// 배포 후: 실제 서버 주소로 교체
const BASE_URL = "http://localhost:8000/api";

export const eventService = {
  /**
   * 이벤트 목록을 가져옵니다.
   * 백엔드: GET /api/events
   */
  getEvents: async (): Promise<ApiResponse<Event[]>> => {
    // axios.get(URL) 은 해당 URL 로 GET 요청을 보냅니다.
    // response.data 가 실제 응답 본문입니다.
    const response = await axios.get(`${BASE_URL}/events`);
    return response.data;
  },

  /**
   * 이벤트 상세를 가져옵니다.
   * 백엔드: GET /api/events/{eventId}
   */
  getEventDetail: async (eventId: string): Promise<ApiResponse<EventDetail>> => {
    const response = await axios.get(`${BASE_URL}/events/${eventId}`);
    return response.data;
  },

  /**
   * 이벤트에 참여합니다.
   * 백엔드: POST /api/events/{eventId}/participate
   */
  participate: async (
    eventId: string
  ): Promise<ApiResponse<ParticipationResult>> => {
    // axios.post(URL) 은 해당 URL 로 POST 요청을 보냅니다.
    // 이 API 는 요청 본문(body)이 필요 없어서 두 번째 인자를 생략합니다.
    const response = await axios.post(
      `${BASE_URL}/events/${eventId}/participate`
    );
    return response.data;
  },
};
