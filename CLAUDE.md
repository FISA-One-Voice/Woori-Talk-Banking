# CLAUDE.md — Woori-Talk-Banking

시각장애인을 위한 음성 기반 뱅킹 앱. React Native (TypeScript) + FastAPI (Python 3.11).  
전체 규칙: [STYLE_GUIDE.md](./STYLE_GUIDE.md)

---

## 프로젝트 구조

```
frontend/         React Native + Expo Router
  app/            파일 위치 = 화면 URL
  components/     공통 UI
  hooks/          useVoiceInput, useTTS 등
  services/       백엔드 API 호출
  store/          Zustand 전역 상태
  types/          TypeScript 타입
backend/app/
  main.py         서버 진입점
  core/config.py  환경변수 (../.env)
  core/exception.py  AppError 및 서브클래스 전체
  core/database.py   DB 세션
  features/       기능별 (router / service / schema)
  shared/voice/   STT·TTS 래퍼
  shared/agent/   LangGraph Agent
  models/         SQLAlchemy ORM
ai/
  asv/            화자 인증 (WavLM) — POST /enroll, /verify
  anti-spoofing/  위조 음성 탐지 — POST /detect
```

---

## 네이밍 규칙

### Frontend (TypeScript)
| 대상 | 형식 |
|------|------|
| 변수·함수 | camelCase |
| 컴포넌트·타입·인터페이스 | PascalCase |
| 상수 | UPPER_SNAKE_CASE |
| 파일(컴포넌트) | PascalCase.tsx |
| 파일(훅·유틸) | camelCase.ts |

### Backend (Python)
| 대상 | 형식 |
|------|------|
| 변수·함수 | snake_case |
| 클래스 | PascalCase |
| 상수 | UPPER_SNAKE_CASE |
| 파일 | snake_case.py |
| API 라우터 prefix | kebab-case (`/voice-auth`) |

---

## 함수 길이

- 권장 ≤ 50줄, 하드 리밋 **80줄**
- 80줄 초과 → 책임 단위로 분리
- 함수 하나 = 책임 하나

---

## 주석

- 복잡한 비즈니스 로직, 외부 API 주의사항, `# TODO:` / `# FIXME:`, 비자명한 결정 이유에만 작성
- 함수명·변수명으로 의도가 전달되면 주석 금지
- 단순 CRUD 주석 금지

---

## API 응답 형식 — 예외 없음

```json
{ "success": true,  "data": {},   "message": "..." }
{ "success": false, "data": null, "message": "...", "code": "ERROR_CODE" }
```

- 실패 응답에는 `code` 필수
- 프론트엔드: `code`로 분기, `message` 문자열 비교 금지
- TTS 메시지 → `getTtsMessage(code)` 위임 (`utils/errorHandler.ts`)

---

## 에러 코드 목록

### 음성·NLU
`VOICE_AUTH_FAILED` · `VOICE_SPOOF_DETECTED` · `STT_FAILED` · `VOICE_PROFILE_ALREADY_EXISTS`  
`VOICE_AUDIO_TOO_LONG` · `VOICE_AUDIO_TOO_LARGE` · `VOICE_AUDIO_INVALID_FORMAT`  
`VOICE_VECTOR_EXTRACT_FAILED` · `ASV_CONFIDENCE_LOW` · `NLU_INTENT_UNRECOGNIZED`

### 계좌
`ACCOUNT_NOT_FOUND` · `ACCOUNT_INSUFFICIENT_BALANCE` · `ACCOUNT_ALIAS_DUPLICATE`

### 송금·거래
`TRANSFER_AMOUNT_INVALID` · `TRANSFER_RECIPIENT_NOT_FOUND` · `TRANSFER_SESSION_INVALID`  
`TRANSFER_IDEMPOTENCY_CONFLICT` · `TX_NOT_FOUND` · `TX_ALREADY_PROCESSED`

### 자동이체
`AUTO_ORDER_SCHEDULE_INVALID` · `AUTO_ORDER_TERMS_NOT_AGREED`  
`AUTO_ORDER_WITHDRAWAL_PASSWORD_INVALID` · `AUTO_ORDER_EXECUTION_FAILED` · `AUTO_ORDER_INVALID_MONTH_END`

### 수취인
`RECIPIENT_NOT_FOUND` · `RECIPIENT_ALIAS_DUPLICATE` · `CONTACT_AMBIGUOUS`

### 사용자·인증
`UNAUTHORIZED` · `USER_NOT_FOUND` · `USER_PHONE_DUPLICATE` · `TOKEN_INVALID` · `TTS_SPEED_OUT_OF_RANGE`

### 공통
`INTERNAL_ERROR` · `INVALID_REQUEST` · `RESOURCE_NOT_FOUND` · `FORBIDDEN` · `RATE_LIMIT_EXCEEDED` · `SERVICE_UNAVAILABLE`

---

## Python 타입 힌트

공개 API·서비스·유틸 함수에 필수. `-> Any` / `-> object` 사용 금지.

```python
def get_user(user_id: int) -> UserSchema | None: ...
async def transfer_money(
    sender_id: int,
    receiver_id: int,
    amount: float,
    memo: str | None = None,
) -> TransferResult: ...
```

---

## Python Docstring (Google 스타일)

라우터·서비스·공개 유틸·공개 클래스에 필수.

```python
async def compare_voice_vector(audio_path: str, user_id: int) -> bool:
    """음성 벡터를 비교하여 인증 여부를 반환합니다.

    Args:
        audio_path: S3에 업로드된 음성 파일 경로.
        user_id: 인증 대상 사용자 ID.

    Returns:
        인증 성공 시 True, 실패 시 False.

    Raises:
        VoiceAuthError: 벡터 비교 중 오류 발생 시.
    """
```

---

## 예외 처리 (Python)

**계층**: `service.py` raise → `router.py` 전파 → `main.py` 처리

```python
# core/exception.py 구조
class AppError(Exception): ...
class AuthError(AppError): pass
class TransferError(AppError): pass
class VoiceServiceError(AppError): pass
class STTError(VoiceServiceError): pass
class TTSError(VoiceServiceError): pass
```

| 규칙 | 내용 |
|------|------|
| router.py에 try/except 금지 | 예외를 자동 전파 |
| `HTTPException(detail={...})` 금지 | 반드시 AppError 서브클래스 사용 |
| 나체 `except:` 금지 | 구체적 타입 명시 |
| assert로 비즈니스 로직 금지 | if + raise 사용 |
| try 블록 최소화 | 실패 가능 줄만 감쌈 |

---

## Frontend 에러 처리 (TypeScript)

| 레이어 | 파일 | 역할 |
|--------|------|------|
| API 에러 | `utils/errorHandler.ts` | code → TTS 메시지 변환 |
| 렌더 크래시 | `components/ErrorBoundary.tsx` | React render 예외 캐치 |

```typescript
// utils/errorHandler.ts — code·메시지 매핑은 여기만
export const getTtsMessage = (code?: string) => MESSAGES[code ?? ''] ?? FALLBACK;

// 화면 컴포넌트
if (!response.data.success) {
  tts(getTtsMessage(response.data.code));
  if (response.data.code === 'UNAUTHORIZED') router.replace('/auth/login');
}
```

---

## Python 가변 기본값

```python
# ❌
def fn(logs: list = []):

# ✅
def fn(logs: list | None = None):
    if logs is None:
        logs = []
```

---

## 환경 변수

루트 `.env` 하나. `backend/app/core/config.py`에서 로드 (`../.env` 참조).  
`.env`는 git 미추적 — 절대 커밋하지 말 것.
