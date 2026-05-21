// =============================================================================
// frontend/types/event.ts
//
// [이 파일의 역할]
// 이벤트 관련 데이터의 형태(타입)를 정의합니다.
// TypeScript 에서 타입을 미리 정의해두면,
// 잘못된 형태의 데이터를 사용할 때 코드 실행 전에 오류를 발견할 수 있습니다.
//
// [다른 파일과의 관계]
// ├─ services/eventService.ts → API 응답 타입으로 사용합니다.
// ├─ store/eventStore.ts      → 상태 타입으로 사용합니다.
// └─ components/EventCard/    → Props 타입으로 사용합니다.
//
// [interface 란?]
// 객체의 모양을 정의하는 TypeScript 문법입니다.
// 예: const event: Event = { event_id: "abc", title: "..." }  → 타입 검사가 자동으로 됩니다.
// =============================================================================

// 이벤트 목록 한 줄에 해당하는 데이터
// 백엔드 schema.py 의 EventSummary 와 대응됩니다.
export interface Event {
  event_id: string;  // UUID 문자열 (예: "550e8400-e29b-41d4-a716-446655440000")
  title: string;
  // 날짜는 ISO 8601 문자열로 옵니다. 예: "2024-01-01T00:00:00"
  // 화면에 표시할 때 new Date(startAt) 로 변환해서 사용합니다.
  start_at: string;
  end_at: string;
  is_active: boolean;
}

// 이벤트 상세 화면에 해당하는 데이터
// Event 를 확장(extends)하므로 Event 의 모든 필드를 포함합니다.
// 백엔드 schema.py 의 EventDetail 과 대응됩니다.
export interface EventDetail extends Event {
  description: string | null;      // 상세 설명 (목록에는 없고 상세에만 있습니다)
  banner_image_url: string | null; // 배너 이미지 URL (없을 수 있습니다)
  participant_count: number;       // 현재까지 참여한 사람 수
}

// 이벤트 참여 성공 시 받는 데이터
// 백엔드 schema.py 의 ParticipationResult 와 대응됩니다.
export interface ParticipationResult {
  event_id: string;
  user_id: string;
  participated_at: string;
}

// 백엔드의 모든 API 가 이 형태로 응답합니다.
// T 는 "제네릭(Generic)"입니다. 호출 시 실제 타입으로 교체됩니다.
// 예: ApiResponse<Event[]>    → data 가 Event 배열
//     ApiResponse<EventDetail> → data 가 EventDetail 하나
export interface ApiResponse<T> {
  success: boolean;
  data: T | null; // 성공 시 실제 데이터, 실패 시 null
  message: string;
  error_code?: string; // 실패 시에만 포함됩니다. (? = 선택 필드)
}
