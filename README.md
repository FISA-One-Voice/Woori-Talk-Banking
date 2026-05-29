# Woori-Talk-Banking

시각장애인을 위한 음성 기반 뱅킹 앱

---

## 개발 환경 세팅

개발 시작 전 [SETUP.md](SETUP.md) 를 참고해서 환경을 세팅해주세요.

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| Frontend | React Native (TypeScript), Expo SDK 55, Expo Router |
| Backend | FastAPI (Python 3.11), SQLAlchemy, Pydantic |
| AI Agent | LangGraph StateGraph, OpenAI gpt-4o-mini |
| STT | Clova Speech API (네이버 클라우드) |
| TTS | Azure Cognitive Services (koreacentral) |
| 화자 인증 | CAM++ ASV — 192차원 임베딩, cosine similarity (임계값 0.6404) |
| 위조음성 탐지 | Anti-spoofing 플레이스홀더 (미구현, 현재 바이패스) |
| Database | PostgreSQL (Aiven) + pgvector |
| 검색/RAG | OpenSearch (Aiven) |
| 전역 상태 | Zustand |
| 암호화 | AES-256-GCM (주민번호, 계좌번호 컬럼) |

---

## 핵심 서비스 흐름

### 1. 일반 음성 뱅킹 흐름

```
[사용자 롱프레스]
       │
       ▼
  [Frontend] _layout.tsx → useVoiceInput → Audio.Recording → WAV/M4A
       │
       ▼
  POST /api/voice  (multipart: audio 파일, Bearer JWT)
       │
       ▼
  [Backend] shared/voice/service.py
       │
       ├─ 1. STT: stt_service.py → Clova Speech API → transcript 텍스트
       │
       ├─ 2. LangGraph: shared/agent/graph.py
       │        intent_node    → GPT-4o-mini 인텐트 분류 + 슬롯 추출
       │        slot_fill_node → 누락 슬롯 질문 생성
       │        resolve_node   → 수취인 alias 검증 (DB 조회)
       │        confirm_node   → 확인 메시지 생성
       │        execute_node   → tool 직접 호출 (mock or 실제)
       │
       └─ 3. TTS: tts_service.py → Azure TTS → base64 MP3
       │
       ▼
  응답: { audio(base64), navigate_to, collected_slots,
          awaiting_confirmation, awaiting_asv_audio, transcript }
       │
       ▼
  [Frontend] _layout.tsx — handleResponse()
       ├─ playBase64Audio(data.audio)           → 사용자가 TTS 음성을 들음
       ├─ router.push(data.navigate_to)         → 해당 화면으로 자동 이동
       └─ voiceResponseStore.setLastResponse()  → 화면 컴포넌트가 슬롯 데이터를 읽음
```

### 2. ASV 화자 인증 흐름 (이체 / 자동이체 확인 후)

```
[사용자 확인 발화] → agent가 ASV_REQUIRED_ACTIONS 해당 인텐트 감지
       │
       ▼
  awaiting_asv_audio=true 응답 반환
       │
  [Frontend] VoiceStatusOverlay: "awaiting_asv" 상태 UI 표시
       │
  [사용자 재발화] → 동일한 POST /api/voice (asv 분기로 진입)
       │
       ▼
  [Backend] asyncio.gather() 병렬 호출
       ├─ POST {ASV_SERVER_URL}/verify  (EC2 CAM++ 서버)
       │    { file: WAV, reference_embedding: 192-dim JSON }
       │    → { is_same_speaker: bool, similarity_score: float }
       │
       └─ POST {ANTI_SPOOFING_EC2_URL}/detect  (현재 USE_ANTI_SPOOFING=False 바이패스)
            → { is_real: true, confidence: 1.0 }  (mock 응답)
       │
       ├─ [인증 성공] execute_node 진행 → 이체 / 자동이체 실행
       │
       └─ [인증 실패] retry_count++ (최대 3회)
               3회 초과 → 작업 취소, 상태 초기화
               미만      → "다시 말씀해 주세요" TTS 반환, awaiting_asv_audio 유지
```

### 3. 음성 등록 흐름

```
[로그인 후 hasVoiceRegistered=false]
       │
       ▼
  [Frontend] app/dev/voice-register.tsx
       │  3회 녹음 진행
       │
       ▼
  POST /api/voice/register  (multipart: WAV 파일, Bearer JWT)
       │
       ▼
  [Backend] features/voice/service.py
       │
       ├─ POST {ASV_SERVER_URL}/enroll  (EC2 CAM++ 서버)
       │    { file: WAV }  → { embedding: [float × 192] }
       │
       └─ DB 저장: users.embedding_vector = 192차원 벡터 (pgvector)
       │
       ▼
  응답: { success: true, data: null, message: "음성 벡터 등록 완료" }
       │
       ▼
  [Frontend] router.replace('/dev') → 로그인 화면으로 이동
```

### 4. 로그인 흐름

```
[Frontend] app/dev/login.tsx
       │
       ├─ Step 1: 전화번호 11자리 입력  (AccessibleNumKeypad)
       ├─ Step 2: PIN 6자리 입력
       │
       ▼
  POST /api/users/login  { phone, pin }
       │
       ▼
  [Backend] features/jwt_auth/service.py
       │  users 테이블 phone_number 조회 → bcrypt PIN 검증
       │  create_access_token() + create_refresh_token()
       │
       ▼
  응답: { accessToken, refreshToken, userId, hasVoiceRegistered }
       │
       ▼
  authStore.setTokens()  → axios 인터셉터가 이후 모든 요청에 자동 첨부
       │
       ├─ hasVoiceRegistered=true  → router.replace('/home')
       └─ hasVoiceRegistered=false → router.replace('/dev/voice-register')
```

---

## 디렉토리 구조

```
Woori-Talk-Banking/
│
├── .env                              # API 키 전체
├── STYLE_GUIDE.md                    # 코딩 컨벤션
│
├── frontend/                         # React Native + TypeScript + Expo Router
│   ├── .env                              # PUBLIC EXPO URL
│   ├── app/
│   │   ├── _layout.tsx               # 루트 레이아웃: 롱프레스 녹음, TTS 재생, 화면 이동
│   │   ├── index.tsx                 # 개발 런처 (프로덕션: /home 리디렉션)
│   │   ├── home/
│   │   │   └── index.tsx             # 홈 화면: 퀵메뉴, TTS 버블, TabBar
│   │   └── dev/
│   │       ├── index.tsx             # 개발 메뉴
│   │       ├── login.tsx             # 전화번호 + PIN 로그인
│   │       └── voice-register.tsx    # 음성 등록 (3회 녹음 → ASV enroll)
│   │
│   ├── components/
│   │   ├── input/
│   │   │   ├── MicButton.tsx         # 마이크 녹음 버튼
│   │   │   ├── HomeVoiceSection.tsx  # 홈 화면 음성 입력 영역
│   │   │   └── AccessibleNumKeypad.tsx # 접근성 숫자 키패드 (TTS 피드백 포함)
│   │   ├── display/
│   │   │   ├── VoiceQuickMenuGrid.tsx
│   │   │   ├── QuickMenuGrid.tsx
│   │   │   ├── InfoBox.tsx
│   │   │   ├── SummaryBox.tsx
│   │   │   └── ActionButton.tsx
│   │   ├── feedback/
│   │   │   ├── TtsBubble.tsx         # TTS 메시지 말풍선
│   │   │   ├── VoiceWaveAnimation.tsx # 녹음 중 파형 애니메이션
│   │   │   ├── LoadingDots.tsx
│   │   │   ├── ResultScreen.tsx
│   │   │   └── StatusBadge.tsx
│   │   ├── layout/
│   │   │   ├── TabBar.tsx            # 하단 탭 (홈/내역/알림/내정보)
│   │   │   ├── TopBar.tsx
│   │   │   ├── AppScreenHeader.tsx
│   │   │   └── StepIndicator.tsx
│   │   └── VoiceStatusOverlay.tsx    # 플로팅 음성 상태 오버레이
│   │
│   ├── hooks/
│   │   └── useVoiceInput.ts          # 롱프레스 → 녹음 → voiceService 업로드
│   ├── services/
│   │   ├── voiceService.ts           # POST /api/voice (통합 음성 파이프라인)
│   │   └── voice.ts                  # POST /api/voice/register (ASV 등록)
│   ├── store/
│   │   ├── authStore.ts              # Zustand: JWT 액세스/리프레시 토큰
│   │   └── voiceResponseStore.ts     # Zustand: 마지막 VoiceResponseData
│   ├── types/
│   │   └── voice.ts                  # VoiceResponseData, VoiceResponse 타입
│   ├── constants/
│   │   ├── homeMenu.ts               # 홈 퀵메뉴 항목 정의
│   │   └── theme.ts                  # COLORS, FONT_SIZES, LAYOUT 상수
│   └── utils/
│       ├── api.ts                    # axios 인스턴스 + 토큰 인터셉터 + Silent Refresh
│       ├── errorHandler.ts           # 에러 코드 → 한국어 TTS 메시지 매핑 (단일 진실 공급원)
│       └── navigateHomeMenu.ts       # 홈 퀵메뉴 라우팅 헬퍼
│
├── backend/
│   ├── certs/
│   │   └── aiven-postgre.pem         # Aiven CA 인증서 (Aiven 콘솔에서 직접 다운로드)
│   ├── tests/                        # pytest 테스트 코드
│   └── app/
│       ├── main.py                   # FastAPI 앱: 라우터 등록, 전역 예외 핸들러
│       ├── core/
│       │   ├── config.py             # Pydantic BaseSettings (루트 .env 참조)
│       │   ├── database.py           # SQLAlchemy 엔진, SessionLocal, get_db()
│       │   ├── exception.py          # AppError + 도메인별 하위 에러 클래스 전체
│       │   ├── jwt_utils.py          # JWT 발급/검증, get_current_user_id()
│       │   └── opensearch.py         # OpenSearch 클라이언트 싱글턴
│       ├── shared/
│       │   ├── crypto.py             # AES-256-GCM 암호화/복호화 (PII 컬럼)
│       │   ├── voice/
│       │   │   ├── router.py         # POST /api/voice, /stt, /tts
│       │   │   ├── service.py        # 음성 파이프라인 오케스트레이터 (STT→Agent→TTS)
│       │   │   ├── schema.py         # VoiceRequest/Response, ASVResult, SttRequest/Response 등
│       │   │   ├── stt_service.py    # Clova Speech STT 래퍼
│       │   │   └── tts_service.py    # Azure TTS 래퍼
│       │   └── agent/
│       │       ├── graph.py          # LangGraph StateGraph (5개 노드)
│       │       ├── state.py          # VoiceState TypedDict
│       │       ├── prompts.py        # 시스템 프롬프트
│       │       ├── slot_schema.py    # SLOT_SCHEMA, SCREEN_MAP, ASV_REQUIRED_ACTIONS
│       │       └── tools/
│       │           ├── mock_tools.py    # mock 구현체 (balance, transfer 등 5개)
│       │           └── tool_registry.py # 실제 tool 바인딩 레지스트리
│       ├── features/
│       │   ├── jwt_auth/             # POST /api/users/login, /refresh, PUT /logout
│       │   ├── voice/                # POST /api/voice/register (ASV 등록)
│       │   ├── recipients/           # GET /api/recipients, GET /api/contacts/match
│       │   ├── balance/              # 미구현 — 담당자 개발 예정
│       │   ├── transfer/             # 미구현 — 담당자 개발 예정
│       │   ├── auto_transfer/        # 미구현 — 담당자 개발 예정
│       │   ├── history/              # 미구현 — 담당자 개발 예정
│       │   ├── event/                # 라우터 주석 처리 — 재구현 예정
│       │   └── admin/                # 미구현
│       └── models/
│           ├── user.py               # User (pgvector 192차원 임베딩 포함)
│           ├── account.py            # Account
│           ├── recipient.py          # RegisteredRecipient
│           ├── transaction.py        # Transaction
│           ├── standing_order.py     # StandingOrder
│           └── event.py              # Event, EventParticipation
│
└── ai/
    ├── asv/                          # EC2 독립 배포 — CAM++ 화자 인증 서버
    │   ├── main.py                   # FastAPI: GET /health, POST /enroll, POST /verify
    │   ├── model.py                  # ASVModel: 임베딩 추출 + cosine 유사도 계산
    │   ├── config.py                 # ASV_THRESHOLD=0.6404
    │   └── Dockerfile                # CPU-only PyTorch, 모델 사전 다운로드, port 8000
    └── anti-spoofing/
        └── .gitkeep                  # 미구현 플레이스홀더
```