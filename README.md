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
| AI Agent | LangGraph Supervisor + SubGraph, OpenAI gpt-4o-mini |
| STT | Clova Speech API (네이버 클라우드) |
| TTS | Azure Cognitive Services (koreacentral) |
| 화자 인증 | CAM++ ASV — 192차원 임베딩, cosine similarity (임계값 0.6404) |
| Database | PostgreSQL (Aiven) + pgvector |
| 검색/RAG | OpenSearch (Aiven) |
| 전역 상태 | Zustand |
| 암호화 | AES-256-GCM (주민번호, 계좌번호 컬럼) |
| 세션 공유 | Redis (LangGraph AsyncRedisSaver checkpointer) |
| 스케줄러 | APScheduler (자동이체 매일 14:30 실행) |
| 모니터링 | Prometheus + Grafana |

---

## 핵심 서비스 흐름

### 1. 음성 뱅킹 흐름

```
[사용자 롱프레스]
       │
       ▼
  [Frontend] useVoiceInput → 녹음 → WAV/M4A
       │
       ▼
  POST /api/voice  (multipart: audio 파일, Bearer JWT)
       │
       ▼
  [Backend] shared/voice/service.py
       │
       ├─ 1. STT → Clova Speech API → transcript
       │
       ├─ 2. LangGraph Supervisor
       │        domain_classify (GPT-4.1-nano)
       │        ┌─ TransferSubGraph    슬롯 수집 → ASV → 이체 실행
       │        ├─ AssetSubGraph       잔액·내역·지출 조회
       │        └─ ConsultationSubGraph RAG 기반 금융 상담
       │
       └─ 3. TTS → Azure → base64 MP3
       │
       ▼
  응답: { audio, navigate_to, collected_slots, awaiting_asv_audio, transcript }
       │
       ▼
  [Frontend] _layout.tsx handleResponse()
       ├─ playBase64Audio()     TTS 재생
       ├─ router.push()         화면 자동 이동
       └─ voiceResponseStore    슬롯 데이터 전달
```

### 2. ASV 화자 인증 흐름 (이체 확인 후)

```
[이체 의도 감지] → Supervisor: awaiting_asv_audio=true 반환
       │
  [Frontend] VoiceStatusOverlay: "awaiting_asv" 상태 표시
       │
  [사용자 재발화] → POST /api/voice (ASV 분기)
       │
       ▼
  [Backend] asyncio.gather() 병렬 호출
       ├─ POST {ASV_SERVER_URL}/verify  (EC2 CAM++ 서버)
       │    → { is_same_speaker: bool, similarity_score: float }
       │
       └─ POST {ANTI_SPOOFING_EC2_URL}/detect  (USE_ANTI_SPOOFING=False 바이패스)
       │
       ├─ [인증 성공] execute_node → 이체 실행
       └─ [인증 실패] retry_count++ (최대 3회) → 초과 시 작업 취소
```

---

## 디렉토리 구조

```
Woori-Talk-Banking/
├── frontend/
│   ├── app/            # Expo Router 화면 (파일명 = 라우트)
│   ├── components/     # 공유 컴포넌트
│   ├── hooks/          # 커스텀 훅
│   ├── services/       # 백엔드 API 호출
│   ├── store/          # Zustand 전역 상태
│   ├── types/          # TypeScript 타입
│   └── utils/          # 공통 유틸리티
│
├── backend/
│   └── app/
│       ├── main.py     # FastAPI 앱 진입점
│       ├── core/       # 설정, DB, JWT, 예외 처리
│       ├── shared/     # 음성 파이프라인(STT/TTS), LangGraph Agent
│       ├── features/   # 화면 단위 기능 모듈 (router / service / schema)
│       └── models/     # SQLAlchemy ORM 모델
│
├── ai/
│   └── asv/            # CAM++ 화자 인증 서버 (EC2 독립 배포)
│
└── infra/              # Prometheus + Grafana 로컬 관측성 스택
```
