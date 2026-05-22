# SCR-007 데이터 흐름 보고서

작성일: 2026-05-21  
작성자: Tech Lead (이남길)  
대상 독자: 팀원 전원 — 특히 처음 프론트·백엔드를 접하는 분

---

## 1\. 전체 흐름 개요

\[사용자 행동\]

    │

    ▼

\[화면 (app/event/)\]          React Native \+ Expo Router

    │  useState / useEffect

    ▼

\[스토어 (store/eventStore)\]  Zustand 전역 상태

    │  fetchEvents / fetchEventDetail / participate

    ▼

\[서비스 (services/eventService)\]  axios HTTP 클라이언트

    │  GET /api/events

    │  GET /api/events/{event\_id}

    │  POST /api/events/{event\_id}/participate

    ▼

\[라우터 (features/event/router)\]  FastAPI 엔드포인트

    │  Depends(get\_db) → DB 세션 주입

    ▼

\[서비스 (atures/event/service)\]  비즈니스 로직

    │  SQLAlchemy ORM 쿼리

    ▼

\[모델 (models/event)\]  DB 테이블

    ▼  
    │  SQLite (개발) / PostgreSQL (운영)

\[DB\]

---

## 2\. 화면 1 — 이벤트 목록 조회 (`GET /api/events`)

### 2-1. 백엔드 처리 단계

① router.py: list\_events() 호출

      │  db \= Depends(get\_db) → 요청마다 새 DB 세션 생성

      ▼

② service.py: get\_event\_list(db)

      │  SELECT \* FROM events

      │  WHERE is\_active \= TRUE

      │  ORDER BY created\_at DESC

      ▼

③ router.py: ORM 객체 → EventSummary(Pydantic) 변환

      │  \[Event 객체\] → EventSummary { event\_id, title, start\_at, end\_at, is\_active }

      ▼

④ router.py: ApiResponse 래퍼로 포장

      │  { success: true, data: \[...\], message: "이벤트 3개를 불러왔습니다." }

      ▼

⑤ FastAPI: JSON 직렬화 → HTTP 200 응답

### 2-2. 프론트엔드 처리 단계

① index.tsx: useEffect → fetchEvents() 호출 (화면 마운트 시 1회)

      ▼

② store/eventStore: fetchEvents()

      │  set({ isLoading: true })

      ▼

③ services/eventService: axios.get('/api/events')

      │  HTTP 요청 발송

      ▼

④ (서버 응답 수신)

      ▼

⑤ store/eventStore: response.success 확인

      │  성공 → set({ events: response.data })

      │  실패 → set({ errorCode: response.error\_code })

      │  항상 → set({ isLoading: false })

      ▼

⑥ index.tsx: 스토어 변화 감지 → 자동 리렌더링

      │  isLoading=false \+ events=\[...\] → EventCard 목록 표시

      │  isLoading=false \+ events=\[\]   → EmptyState 표시

### 2-3. 응답 예시

{

  "success": true,

  "data": \[

    {

      "event\_id": "550e8400-e29b-41d4-a716-446655440001",

      "title": "신규 가입 환영 이벤트",

      "start\_at": "2026-05-19T00:00:00",

      "end\_at": "2026-06-20T00:00:00",

      "is\_active": true

    }

  \],

  "message": "이벤트 3개를 불러왔습니다.",

  "error\_code": null

}

---

## 3\. 화면 2 — 이벤트 상세 조회 (`GET /api/events/{event_id}`)

### 3-1. 백엔드 처리 단계

① router.py: get\_event(event\_id: str)

      │  event\_id는 URL 경로 파라미터 (UUID 문자열)

      ▼

② service.py: get\_event\_detail(db, event\_id)

      │  SELECT \* FROM events WHERE event\_id \= '{uuid}'

      │  없으면 → HTTPException(404, {"error": "EVENT\_NOT\_FOUND"})

      ▼

③ main.py 전역 예외 핸들러 (오류 시):

      │  HTTPException.detail\["error"\] 꺼내기

      │  → { success: false, data: null, message: "...", error\_code: "EVENT\_NOT\_FOUND" }

      ▼

③ router.py (성공 시): ORM 객체 → EventDetail(Pydantic) 변환

      │  participant\_count \= len(event.participations)

      │  (SQLAlchemy relationship으로 JOIN 없이 참여 수 집계)

      ▼

④ ApiResponse 래퍼 → JSON 직렬화 → HTTP 200 응답

### 3-2. 프론트엔드 처리 단계

① \[id\].tsx: useEffect → fetchEventDetail(id) 호출

      │  id \= URL 경로의 UUID 문자열 (useLocalSearchParams)

      │  예: /event/550e8400-... → id \= "550e8400-..."

      ▼

② store/eventStore: fetchEventDetail(eventId: string)

      │  set({ isLoading: true, selectedEvent: null })

      ▼

③ services/eventService: axios.get('/api/events/{eventId}')

      ▼

④ store/eventStore: 응답 처리

      │  성공 → set({ selectedEvent: response.data })

      │  실패 → set({ errorCode: response.error\_code })

      ▼

⑤ \[id\].tsx: 조건부 렌더링

      │  isLoading && \!selectedEvent → ActivityIndicator

      │  selectedEvent 있음          → 상세 화면 (제목/기간/참여자/설명)

      │  \!selectedEvent (오류)        → "찾을 수 없습니다" 안내

### 3-3. 응답 예시

{

  "success": true,

  "data": {

    "event\_id": "550e8400-e29b-41d4-a716-446655440001",

    "title": "신규 가입 환영 이벤트",

    "description": "우리톡뱅킹에 처음 가입하신 고객님께...",

    "banner\_image\_url": null,

    "start\_at": "2026-05-19T00:00:00",

    "end\_at": "2026-06-20T00:00:00",

    "is\_active": true,

    "participant\_count": 0

  },

  "message": "이벤트 상세를 불러왔습니다.",

  "error\_code": null

}

---

## 4\. 화면 3 — 이벤트 참여 (`POST /api/events/{event_id}/participate`)

### 4-1. 백엔드 처리 단계 (3단계 검증)

① router.py: participate(event\_id: str, user\_id: str)

      │  user\_id \= Depends(get\_current\_user) → 현재는 고정 UUID

      ▼

② service.py: participate\_event(db, event\_id, user\_id)

      │

      │ \[검증 1\] 이벤트 존재 여부

      │   SELECT \* FROM events WHERE event\_id \= '{uuid}'

      │   없으면 → 404 EVENT\_NOT\_FOUND

      │

      │ \[검증 2\] 이벤트 기간 확인

      │   now \> event.end\_at 이면 → 409 EVENT\_ENDED

      │

      │ \[검증 3\] 중복 참여 확인

      │   SELECT \* FROM event\_participations

      │   WHERE event\_id \= '{uuid}' AND user\_id \= '{uuid}'

      │   있으면 → 409 ALREADY\_PARTICIPATED

      │

      │ \[통과\] 참여 기록 생성

      │   INSERT INTO event\_participations (participation\_id, event\_id, user\_id, participated\_at)

      │   VALUES (uuid4(), '{event\_id}', '{user\_id}', now())

      ▼

③ router.py: ParticipationResult 조립 → ApiResponse 래퍼 → HTTP 200

### 4-2. 프론트엔드 처리 단계

① \[id\].tsx: '참여하기' 버튼 탭 → handleParticipate()

      │  isParticipating \= true (중복 탭 방지)

      ▼

② store/eventStore: participate(eventId: string)

      │  → { success: boolean, errorCode?: string } 반환

      │  (스토어에 저장하지 않고 결과만 반환 — 화면 전용 상태이기 때문)

      ▼

③ services/eventService: axios.post('/api/events/{eventId}/participate')

      ▼

④ \[id\].tsx: 결과 분기

      │

      │  result.success \= true

      │    → setIsSuccess(true)

      │    → SuccessScreen 전체 화면 전환

      │    → 확인 버튼 → router.back() (목록으로 복귀)

      │

      │  result.success \= false

      │    → toErrorType(result.errorCode) 호출

      │       'ALREADY\_PARTICIPATED' → 'already'

      │       'NETWORK\_ERROR'        → 'network'

      │       그 외                  → 'server'

      │    → setErrorType(...) → ErrorModal 팝업 표시

### 4-3. 응답 예시 — 성공

{

  "success": true,

  "data": {

    "event\_id": "550e8400-e29b-41d4-a716-446655440001",

    "user\_id": "00000000-0000-0000-0000-000000000001",

    "participated\_at": "2026-05-21T09:30:00"

  },

  "message": "이벤트 참여가 완료되었습니다.",

  "error\_code": null

}

### 4-4. 응답 예시 — 실패 (중복 참여)

{

  "success": false,

  "data": null,

  "message": "이미 참여한 이벤트입니다.",

  "error\_code": "ALREADY\_PARTICIPATED"

}

---

## 5\. 오류 처리 흐름 (공통)

service.py

  raise HTTPException(status\_code=409, detail={"error": "ALREADY\_PARTICIPATED"})

      │

      ▼

main.py — @app.exception\_handler(HTTPException)

  detail\["error"\] 꺼냄 → error\_code \= "ALREADY\_PARTICIPATED"

  ERROR\_MESSAGES 딕셔너리에서 한국어 메시지 조회

      │

      ▼

JSON 응답

  { success: false, data: null, message: "이미 참여한 이벤트입니다.", error\_code: "ALREADY\_PARTICIPATED" }

      │

      ▼

eventStore.participate()

  return { success: false, errorCode: "ALREADY\_PARTICIPATED" }

      │

      ▼

\[id\].tsx — toErrorType("ALREADY\_PARTICIPATED")

  → ErrorType \= 'already'

      │

      ▼

\<ErrorModal type="already" /\>

  제목: "이미 참여한 이벤트"

  메시지: "이 이벤트는 이미 참여하셨습니다."

**핵심 원칙**: 프론트엔드는 `error_code`로만 분기합니다. `message` 문자열로 분기하면 백엔드 메시지가 바뀔 때 프론트도 깨집니다.

---

## 6\. DB ↔ Pydantic ↔ TypeScript 타입 대응표

| DB 컬럼 (DBML) | SQLAlchemy 모델 | Pydantic 스키마 | TypeScript 타입 |
| :---- | :---- | :---- | :---- |
| `event_id uuid` | `event_id: str` | `event_id: str` | `event_id: string` |
| `title varchar` | `title: str` | `title: str` | `title: string` |
| `start_at timestamp` | `start_at: datetime` | `start_at: datetime` | `start_at: string` |
| `end_at timestamp` | `end_at: datetime` | `end_at: datetime` | `end_at: string` |
| `is_active boolean` | `is_active: bool` | `is_active: bool` | `is_active: boolean` |
| `description text` | `description: str | None` | `description: str | None` | `description: string | null` |
| `banner_image_url varchar` | `banner_image_url: str | None` | `banner_image_url: str | None` | `banner_image_url: string | null` |
| *(집계값)* | `len(participations)` | `participant_count: int` | `participant_count: number` |

**날짜 타입 주의**: 백엔드에서 `datetime` → JSON 직렬화 시 ISO 8601 문자열(`"2026-05-21T09:30:00"`)로 변환됩니다. 프론트엔드 타입은 `string`이며, 화면에서 `new Date(start_at).toLocaleDateString('ko-KR')` 으로 변환합니다.

---

## 7\. 백엔드 MVC 유사 패턴 — "누가 무엇을 담당하는가"

### 7-1. MVC란 무엇인가

MVC(Model-View-Controller)는 코드를 역할에 따라 세 덩어리로 나누는 설계 방식입니다.

Model      → 데이터 구조 정의 \+ DB 접근

View       → 화면에 결과를 보여주는 부분

Controller → 요청을 받아 Model과 View를 연결

웹 API에서는 "View(화면)"가 없으므로, FastAPI는 MVC를 아래와 같이 변형해서 씁니다.

### 7-2. 이 프로젝트의 백엔드 패턴 — Router \+ Service \+ Model

HTTP 요청

    │

    ▼

router.py  ←── Controller 역할

    │  "이 URL이 오면 이 함수를 실행한다"

    │  요청을 받아 service로 넘기고, 결과를 ApiResponse로 포장해서 반환

    │  업무 규칙을 직접 판단하지 않음

    ▼

service.py  ←── Service 역할 (MVC에 없는 계층, 실무에서 추가)

    │  "업무 규칙을 판단한다"

    │  중복 참여인가? 기간이 지났는가? — 모든 비즈니스 결정이 여기에 있음

    │  HTTP와 무관하게 순수 Python 함수로만 작성

    │  오류가 있으면 HTTPException을 올려보냄

    ▼

models/event.py  ←── Model 역할

    │  "DB 테이블 구조를 Python 클래스로 표현한다"

    │  Event 클래스 \= events 테이블

    │  EventParticipation 클래스 \= event\_participations 테이블

    │  DB에 어떤 컬럼이 있는지 정의만 함 — 쿼리 실행은 하지 않음

    ▼

schema.py  ←── DTO(Data Transfer Object) 역할

    │  "API 요청/응답 형태를 Pydantic으로 정의한다"

    │  EventSummary, EventDetail, ApiResponse 등

    │  ORM 객체(DB 행)를 API 응답 JSON으로 변환하는 중간 다리

### 7-3. `service.py`가 왜 따로 있는가

MVC에서 Controller(router.py)에 업무 규칙을 몰아넣으면 하나의 파일이 수백 줄이 됩니다. 이를 막기 위해 **업무 규칙만 뽑아낸 Service 계층**을 추가합니다.

`service.py`가 담당하는 것:

def participate\_event(db, event\_id, user\_id):

    \# ① 이벤트가 존재하는가?

    event \= get\_event\_detail(db, event\_id)          \# 없으면 404

    \# ② 이벤트 기간이 지나지 않았는가?

    if datetime.now() \> event.end\_at:

        raise HTTPException(409, {"error": "EVENT\_ENDED"})

    \# ③ 이미 참여한 적이 없는가?

    already \= db.query(EventParticipation).filter(...).first()

    if already:

        raise HTTPException(409, {"error": "ALREADY\_PARTICIPATED"})

    \# ④ 위 세 조건 모두 통과 → 참여 기록 생성

    participation \= EventParticipation(event\_id=event\_id, user\_id=user\_id)

    db.add(participation)

    db.commit()

    return participation

router.py는 이 함수를 호출하기만 합니다. "언제 409를 반환하는가"는 router.py가 모릅니다.

**이렇게 분리하면**: 중복 참여 규칙을 바꿀 때 `service.py`만 수정하면 됩니다. router.py, 화면, 스토어는 건드리지 않아도 됩니다.

---

## 8\. 프론트엔드의 역할 — "표시만 한다"

### 8-1. 프론트엔드가 하는 것 vs 하지 않는 것

백엔드가 결정하는 것 (service.py)        프론트엔드가 결정하는 것 (화면 파일)

──────────────────────────────────       ──────────────────────────────────

✓ 이벤트가 유효한가?                      ✓ 어떤 컴포넌트로 보여줄까?

✓ 기간이 지났는가?                        ✓ 로딩 중에 스피너를 보여줄까?

✓ 이미 참여한 사용자인가?                  ✓ 오류를 어떤 모달 타입으로 보여줄까?

✓ 참여 기록을 DB에 저장한다               ✓ 날짜를 "2026년 5월 21일"로 포맷한다

✓ 어떤 에러 코드를 내보낼지               ✗ 규칙 판단은 일절 없음

### 8-2. 프론트엔드에 있는 두 가지 UI 로직

프론트엔드가 백엔드 응답을 그대로 표시하지 않고 변환하는 경우가 두 가지 있습니다.  
이 둘은 "어떻게 보여줄까"에 관한 UI 로직이지, 업무 규칙이 아닙니다.

**① 에러 코드 → 모달 타입 변환** (`app/event/[id].tsx`)

function toErrorType(errorCode: string | undefined): ErrorType {

  if (errorCode \=== 'ALREADY\_PARTICIPATED') return 'already';

  if (errorCode \=== 'NETWORK\_ERROR')        return 'network';

  return 'server';

}

백엔드의 `ALREADY_PARTICIPATED`가 어떤 한국어 메시지로 표시되는지는 백엔드가 결정합니다.  
프론트엔드는 "이 코드가 왔을 때 어떤 **UI 컴포넌트**를 쓸까"만 결정합니다.

**② 날짜 포맷 변환** (`app/event/[id].tsx`)

function formatDate(dateStr: string): string {

  return new Date(dateStr).toLocaleDateString('ko-KR', {

    year: 'numeric', month: 'long', day: 'numeric',

  });

}

// "2026-05-19T00:00:00" → "2026년 5월 19일"

백엔드는 ISO 8601 형식으로 날짜를 보냅니다. 이를 어떤 언어/형식으로 표시할지는 화면의 문제이므로 프론트엔드에 있습니다.

### 8-3. 전체 책임 분리 요약

사용자

  │  탭/입력

  ▼

\[화면 (app/)\]

  │  "어떻게 보여줄까" — 렌더링만 담당

  │  업무 규칙 없음, UI 표현 로직(에러타입 변환, 날짜 포맷)만 있음

  ▼

\[스토어 (store/)\] \+ \[서비스 (services/)\]

  │  "언제 API를 호출하고 상태를 어디에 저장할까"

  ▼

─────── 네트워크 경계 ───────

  ▼

\[router.py\]    "어떤 URL → 어떤 함수"

  ▼

\[service.py\]   ★ 모든 업무 규칙이 여기에 있음 ★

  ▼

\[models.py\]    "DB 테이블 \= Python 클래스"

  ▼

\[DB\]

**팀원에게 한 줄 요약**: 화면 파일을 수정하면 보이는 것이 바뀌고, `service.py`를 수정하면 규칙이 바뀝니다. 이 두 가지는 서로 건드리지 않습니다.

---

## 9\. 계층별 단일 책임 — 어느 파일을 열어야 하는가

각 파일은 딱 하나의 일만 합니다. 수정할 때 어느 파일을 열어야 할지 판단하는 기준입니다.

| 파일 | 단 하나의 책임 | 하지 않는 것 |
| :---- | :---- | :---- |
| `app/event/index.tsx` | **보여주기** — 스토어에서 꺼낸 데이터를 화면에 렌더링 | 데이터를 직접 가져오거나 저장하지 않음 |
| `store/eventStore.ts` | **상태 관리** — 로딩/에러/데이터를 전역 보관 | HTTP 요청을 직접 하지 않음 |
| `services/eventService.ts` | **HTTP 통신** — URL과 메서드를 모아서 axios 호출 | 데이터를 저장하거나 화면을 건드리지 않음 |
| `features/event/router.py` | **URL 매핑** — 어떤 URL이 오면 어떤 함수를 실행할지 | 업무 규칙 판단 없음 |
| `features/event/service.py` | **업무 규칙** — 중복 검사, 기간 확인 등 | HTTP 요청/응답 처리 없음 |
| `models/event.py` | **DB 구조 정의** — 테이블 \= 클래스, 컬럼 \= 속성 | 쿼리 실행 없음 (실행은 service.py) |

**실전 적용**: API 주소가 바뀌면 `eventService.ts`만, 중복 참여 규칙이 바뀌면 `service.py`만 수정합니다.

---

## 10\. 계층을 지나며 바뀌는 데이터 형태

같은 데이터가 계층마다 다른 모양을 가집니다.

PostgreSQL DB

  └─ 행(row): event\_id='550e...', title='환영 이벤트', is\_active=1, ...

        ↓  SQLAlchemy ORM이 자동 변환

백엔드 service.py

  └─ Python 객체: Event(event\_id='550e...', title='환영 이벤트', is\_active=True, ...)

        ↓  router.py에서 Pydantic Schema로 필드 선별

백엔드 router.py

  └─ Pydantic: EventSummary(event\_id=..., title=..., start\_at=..., end\_at=..., is\_active=...)

        ↓  FastAPI가 자동으로 JSON 문자열로 변환

네트워크 (HTTP 응답)

  └─ JSON: {"event\_id":"550e...","title":"환영 이벤트","is\_active":true,...}

        ↓  axios가 파싱 → TypeScript 타입 적용

프론트엔드 store

  └─ TS 객체: Event { eventId: string, title: string, isActive: boolean, ... }

        ↓  화면이 구독

화면 (app/event/index.tsx)

  └─ \<EventCard title={event.title} ... /\>

**EventSummary가 필터 역할을 합니다.** `Event` ORM 모델에는 `description`, `banner_image_url` 등 모든 컬럼이 있지만, 목록 화면에 불필요한 필드는 `EventSummary`에 포함하지 않아 응답 크기를 줄입니다. 상세 화면에서만 `EventDetail`을 씁니다.

### ORM이 Python 코드를 SQL로 변환하는 예시

\# service.py에서 이렇게 씁니다 (Python)

db.query(Event)

  .filter(Event.is\_active \== True)

  .order\_by(Event.created\_at.desc())

  .all()

SQLAlchemy가 위 코드를 아래 SQL로 자동 변환해서 실행합니다:

SELECT \* FROM events

WHERE is\_active \= TRUE

ORDER BY created\_at DESC;

SQL을 직접 작성하지 않아도 되고, DB가 SQLite에서 PostgreSQL로 바뀌어도 Python 코드는 그대로 유지됩니다.  
