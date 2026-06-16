# Style Guide

> React Native (TypeScript) + FastAPI (Python) — detailed reference  
> Python rules based on [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)  
> Quick summary → [CLAUDE.md](./CLAUDE.md)

---

## 1. Naming Conventions

### 1.1 Naming Rules

#### Frontend (TypeScript)

| Target | Case | Example |
|--------|------|---------|
| Variable / Function | camelCase | `userName`, `fetchUserData()` |
| Component | PascalCase | `VoiceAuthModal`, `TransferForm` |
| Type / Interface | PascalCase | `UserProfile`, `ApiResponse` |
| Constant | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT`, `API_BASE_URL` |
| CSS class | kebab-case | `voice-auth-button`, `transfer-form` |
| File (component) | PascalCase | `VoiceAuthModal.tsx` |
| File (util / hook) | camelCase | `useVoiceAuth.ts`, `formatCurrency.ts` |

#### Backend (Python)

| Target | Case | Example |
|--------|------|---------|
| Variable / Function | snake_case | `user_id`, `get_voice_vector()` |
| Class | PascalCase | `UserService`, `VoiceAuthRequest` |
| Constant | UPPER_SNAKE_CASE | `MAX_FILE_SIZE`, `STT_TIMEOUT` |
| File | snake_case | `voice_auth.py`, `user_router.py` |
| API router prefix | kebab-case | `/voice-auth`, `/asset-inquiry` |

---

## 2. Function Length

- **Recommended: ≤ 50 lines. Hard limit: 80 lines.**
- Over 80 lines → split by responsibility unit.
- One function = one responsibility.

```python
# ❌ Bad — too much in one function
async def handle_voice_auth(audio_file):
    # file save logic   20 lines
    # STT conversion    20 lines
    # voice vector comparison    20 lines
    # DB save           20 lines  ← exceeds 80 lines

# ✅ Good — split by responsibility
async def handle_voice_auth(audio_file):
    saved_path = await save_audio_file(audio_file)
    transcript = await convert_to_text(saved_path)
    is_verified = await compare_voice_vector(saved_path)
    await save_auth_log(is_verified)
    return is_verified
```

---

## 3. Comments

### 3.1 When to Comment
- Complex business logic
- External API integration caveats
- Temporary code (`# TODO:`, `# FIXME:`)
- Non-obvious reason behind a decision
- Execution order that must not change
- Intentionally omitted error handling

### 3.2 When NOT to Comment
- When the function/variable name already makes intent clear
- Simple CRUD logic

```python
# ✅ Good — explains the why
# NAVER CLOVA STT supports a maximum of 60 seconds; validate length before calling
if audio_duration > 60:
    raise ValueError("음성은 60초를 초과할 수 없습니다.")

# ❌ Bad — just reads the code aloud
# get user_id
user_id = get_user_id()
```

```typescript
// TODO: Card history TTS notification feature (2024 Q2)
// FIXME: Recording cuts off when app goes to background during voice recording
```

---

## 4. API Response Format

All endpoints use the same envelope — no exceptions.

### 4.1 Success

```json
{
  "success": true,
  "data": { },
  "message": "요청이 성공적으로 처리되었습니다."
}
```

### 4.2 Failure

```json
{
  "success": false,
  "data": null,
  "message": "음성 인증에 실패했습니다.",
  "code": "VOICE_AUTH_FAILED"
}
```

### 4.3 FastAPI — Writing Responses

```python
# ✅ Success
return ApiResponse(success=True, data=result, message="처리 완료")

# ✅ Failure — code is mandatory
return ApiResponse(
    success=False,
    message="ASV confidence 기준 미달",
    code="ASV_CONFIDENCE_LOW",
)

# ❌ Missing code — client cannot branch
return ApiResponse(success=False, message="인증 실패")
```

### 4.4 Frontend — Handling Errors

```typescript
// ✅ Branch on code, never on message string
const response = await api.post<ApiResponse<VoiceAuthResult>>('/voice/verify-speaker');
if (!response.data.success) {
  switch (response.data.code) {
    case 'ASV_CONFIDENCE_LOW':
      tts('목소리가 잘 인식되지 않았습니다. 다시 말씀해 주세요.');
      break;
    case 'ASV_MAX_ATTEMPTS_EXCEEDED':
      tts('인증에 실패하였습니다. 보안 담당자에게 연락됩니다.');
      break;
    default:
      tts('오류가 발생했습니다. 잠시 후 다시 시도해 주세요.');
  }
}
```

Rules:
- Branch on `code`. Never compare `message` strings.
- Always include a `default` case.
- TTS messages must be user-friendly — no technical terms (e.g., avoid "ASV failure").

---

## 5. Error Code Reference

### 5.1 Voice & STT/TTS

| 에러 코드 | 설명 |
|-----------|------|
| `STT_FAILED` | Clova Speech STT 호출 실패 |
| `VOICE_AUDIO_TOO_LONG` | 음성 파일 길이 초과 — CLOVA STT 60초 제한 |
| `VOICE_AUDIO_TOO_LARGE` | 음성 파일 용량 초과 — STT API 최대 10MB 제한 |
| `VOICE_AUDIO_INVALID_FORMAT` | 지원하지 않는 오디오 포맷 |
| `VOICE_VECTOR_EXTRACT_FAILED` | 음성 벡터(embedding) 추출 실패 — pgvector 저장 전 단계 오류 |
| `SERVICE_UNAVAILABLE` | 외부 서비스 장애 — Clova / Azure TTS |

### 5.2 ASV (화자 인증)

| 에러 코드 | 설명 |
|-----------|------|
| `ASV_NOT_ENROLLED` | 음성 벡터 미등록 — `users.embedding_vector IS NULL` |
| `ASV_SERVER_ERROR` | EC2 CAM++ 서버 오류 응답 |
| `ASV_TIMEOUT` | CAM++ 서버 응답 타임아웃 |

### 5.3 Account & Asset

| 에러 코드 | 설명 |
|-----------|------|
| `ACCOUNT_NOT_FOUND` | 계좌를 찾을 수 없음 |
| `INSUFFICIENT_BALANCE` | 잔액 부족 |
| `INVALID_PERIOD` | 유효하지 않은 조회 기간 |
| `MISSING_CATEGORY` | 카테고리 미지정 |

### 5.4 Transfer & Transaction

| 에러 코드 | 설명 |
|-----------|------|
| `INVALID_ACCOUNT_FORMAT` | 계좌번호 형식 오류 (400) |
| `TRANSFER_ACCOUNT_NOT_FOUND` | 출금 계좌 없음 (404) |
| `TRANSFER_RECIPIENT_NOT_FOUND` | 수취인 계좌 조회 실패 (404) |
| `TRANSFER_PENDING` | 동일 idempotency_key 이체 처리 중 (409) |
| `IDEMPOTENCY_KEY_USED` | 동일 key 이체가 이미 실패 처리됨 — 새 key 필요 (409) |
| `TRANSACTION_NOT_FOUND` | 거래 내역을 찾을 수 없음 (404) |
| `TX_NOT_FOUND` | 거래·지출 내역 없음 (404) |

### 5.5 Auto Transfer (자동이체)

| 에러 코드 | 설명 |
|-----------|------|
| `AUTO_ORDER_ACCOUNT_NOT_FOUND` | 출금 계좌 없음 |
| `AUTO_ORDER_NOT_FOUND` | 자동이체 건 없음 |
| `AUTO_ORDER_STATUS_INVALID` | 상태값 오류 (활성/비활성 외 값) |
| `AUTO_ORDER_TERMS_NOT_AGREED` | 자동이체 약관 미동의 — `terms_agreed_at` 누락 |
| `AUTO_ORDER_WITHDRAWAL_PASSWORD_INVALID` | 출금 계좌 비밀번호 불일치 |

### 5.6 Recipient (수취인)

| 에러 코드 | 설명 |
|-----------|------|
| `RECIPIENT_NOT_FOUND` | 등록 수취인을 찾을 수 없음 |

### 5.7 Event (이벤트)

| 에러 코드 | 설명 |
|-----------|------|
| `EVENT_NOT_FOUND` | 이벤트를 찾을 수 없음 |
| `INVALID_EVENT_ID` | 유효하지 않은 이벤트 ID |
| `ALREADY_PARTICIPATED` | 이미 참여한 이벤트 재참여 시도 |
| `EVENT_FETCH_ERROR` | 이벤트 목록 조회 중 오류 |

### 5.8 Agent & Market

| 에러 코드 | 설명 |
|-----------|------|
| `AGENT_CONFIG_ERROR` | LangGraph 에이전트 설정 오류 |
| `AGENT_CONTRACT_VIOLATION` | 에이전트 상태 계약 위반 |
| `TRANSFER_AGENT_INIT_FAILED` | 이체 에이전트 초기화 실패 |
| `TRANSFER_TOOL_FAILED` | 이체 tool 호출 실패 |
| `TRANSFER_TOOL_NOT_FOUND` | 이체 tool 미등록 |
| `MARKET_API_FAILED` | 시장 정보 API 호출 실패 |
| `MARKET_API_HTTP_ERROR` | 시장 정보 HTTP 오류 |
| `MISSING_API_KEY` | 외부 API 키 누락 |

### 5.9 Search (OpenSearch)

| 에러 코드 | 설명 |
|-----------|------|
| `SEARCH_FAILED` | OpenSearch 검색/색인 중 오류 |
| `INDEX_CREATION_FAILED` | OpenSearch 인덱스 생성 실패 |

### 5.10 User & Authentication

| 에러 코드 | 설명 |
|-----------|------|
| `UNAUTHORIZED` | 인증되지 않은 요청 |
| `USER_NOT_FOUND` | 사용자를 찾을 수 없음 |
| `TOKEN_INVALID` | 토큰 위변조 또는 유효하지 않음 |
| `TTS_SPEED_OUT_OF_RANGE` | TTS 속도 범위 초과 — `tts_speed` CHECK (0.25~4.0) 위반 |

### 5.11 Common

| 에러 코드 | 설명 |
|-----------|------|
| `INTERNAL_ERROR` | 서버 내부 오류 |
| `INVALID_REQUEST` | 요청 파라미터 형식 오류 — Pydantic 검증 실패 |

---

## 6. Type Hints (Python)

Required on all public API, service, and utility functions.

### 6.1 Requirement Table

| Target | Required |
|--------|----------|
| Public API / service / utility functions | ✅ Required |
| FastAPI router | ✅ Required (won't work without) |
| Internal helpers / simple lambdas | Recommended |
| Test code | Optional |

### 6.2 Checklist

```python
# 1. Argument types?
def process(user_id: int, amount: float): ...           # ✅

# 2. Return type?
def get_user(user_id: int) -> UserSchema: ...           # ✅

# 3. None possibility?
def find_user(user_id: int) -> UserSchema | None: ...   # ✅

# 4. ≥ 3 params → line break
async def transfer_money(
    sender_id: int,
    receiver_id: int,
    amount: float,
    memo: str | None = None,
) -> TransferResult: ...
```

### 6.3 Common Patterns

```python
value: str | None = None          # nullable
items: list[UserSchema]           # list
config: dict[str, int]            # dict
async def fetch() -> list[TransactionSchema]: ...
def log_event(event: str) -> None: ...
def parse(value: int | str) -> str: ...
```

Avoid `-> Any` and `-> object` unless absolutely necessary.

---

## 7. Docstrings (Python)

### 7.1 Requirement Table

| Target | Required |
|--------|----------|
| Router functions | ✅ Required |
| Service functions | ✅ Required |
| Public utility functions | ✅ Required |
| Public classes | ✅ Required |
| Internal helper functions | Recommended |
| Simple CRUD functions | Optional |
| Test functions | Optional |

### 7.2 Standard Format

```python
async def compare_voice_vector(audio_path: str, user_id: int) -> bool:
    """음성 벡터를 비교하여 인증 여부를 반환합니다.

    Args:
        audio_path: S3에 업로드된 음성 파일 경로.
        user_id: 인증 대상 사용자 ID.

    Returns:
        인증 성공 시 True, 실패 시 False.

    Raises:
        FileNotFoundError: 음성 파일이 S3에 존재하지 않는 경우.
        VoiceAuthError: 벡터 비교 중 오류가 발생한 경우.
    """
```

### 7.3 Class Docstring

```python
class VoiceAuthService:
    """음성 인증 관련 비즈니스 로직을 처리하는 서비스.

    Attributes:
        db: 데이터베이스 세션.
        s3_client: S3 클라이언트 인스턴스.
    """
```

### 7.4 Common Mistakes

```python
# ❌ Repeating the type
Returns:
    bool

# ❌ Translating the function name
"""compare_voice_vector 함수입니다."""

# ❌ Listing every exception
Raises:
    Exception: 오류 발생 시.

# ✅ Explain the meaning
Returns:
    인증 성공 시 True, 실패 시 False.

# ✅ Action-oriented summary
"""음성 벡터를 비교하여 인증 여부를 반환합니다."""

# ✅ Only explicit raises
Raises:
    VoiceAuthError: 벡터 비교 중 오류 발생 시.
```

> **VSCode tip** — Install `autoDocstring` extension. Typing `"""` under a function auto-generates the Google-style skeleton.

---

## 8. Exception Handling (Python)

### 8.1 Custom Exception Classes — `core/exception.py`

All domain errors inherit from `AppError`. `main.py` handles only `AppError`; all subclasses are caught automatically.

```python
# core/exception.py
class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        user_message: str | None = None,   # TTS 메시지 — 미지정 시 message와 동일
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.user_message = user_message if user_message is not None else message

# ── Voice 서비스 계층 ──────────────────────────────────────────────────────────
class VoiceServiceError(AppError): pass  # shared/voice/ 공통 기반
class STTError(VoiceServiceError): pass  # stt_service.py — Clova STT 실패
class TTSError(VoiceServiceError): pass  # tts_service.py — Azure TTS 실패
class ASVError(VoiceServiceError): pass  # ASV 화자 인증 서버 HTTP 오류 (502 기본)

# ── Feature 계층 (features/ 디렉토리와 1:1 대응) ──────────────────────────────
class AuthError(AppError): pass          # features/jwt_auth/
class BalanceError(AppError): pass       # features/asset/ — 잔액 조회
class HistoryError(AppError): pass       # features/asset/ — 거래 내역 조회
class TransferError(AppError): pass      # features/transfer/
class AutoTransferError(AppError): pass  # features/auto_transfer/
class RecipientError(AppError): pass     # features/recipients/
class EventError(AppError): pass         # features/event/ (기반)
class EventNotFoundError(EventError): pass        # 이벤트 없음
class AlreadyParticipatedError(EventError): pass  # 중복 참여

# ── Shared 인프라 계층 ────────────────────────────────────────────────────────
class AgentError(AppError): pass         # shared/agent/ — LangGraph 초기화·실행
class OpenSearchError(AppError): pass    # core/opensearch.py — 검색·색인
class OpenSearchIndexError(OpenSearchError): pass  # 인덱스 생성 실패
class MarketError(AppError): pass        # features/market/ — 환율·금리 조회
```

> **`user_message` 사용 지침**
> - 기술적 내부 메시지(`message`)와 사용자에게 읽어줄 TTS 메시지(`user_message`)가 다를 때만 명시한다.
> - 음성 파이프라인(voice router)이 `AppError.user_message`를 TTS로 변환해 반환하므로 서비스 레이어에서 사용자 친화적 문구를 직접 지정할 수 있다.
> ```python
> raise TransferError(
>     code="INSUFFICIENT_BALANCE",
>     message="balance < amount",          # 로그·디버그용
>     status_code=400,
>     user_message="잔액이 부족합니다.",   # TTS로 변환되는 사용자 메시지
> )
> ```

### 8.2 Rules

| Rule | Detail |
|------|--------|
| `service.py` raises, `router.py` propagates, `main.py` handles | Exceptions always flow upward |
| All domain exceptions inherit from `AppError` | `HTTPException(detail={...})` forbidden |
| No `try/except` in `router.py` | Let exceptions propagate automatically |
| No bare `except:` | Always specify concrete exception type |
| Minimize `try` blocks | Wrap only lines that can fail |
| No business logic with `assert` | Use `if` + `raise` instead |

### 8.3 Pattern

```python
# service.py — raise AppError subclass, never catch
async def speech_to_text(audio_bytes: bytes) -> str:
    try:
        result = await clova_api.recognize(audio_bytes)
    except Exception:
        raise STTError(code="STT_FAILED", message="음성 인식 실패", status_code=502)

    if not result:
        raise STTError(code="STT_EMPTY_RESULT", message="인식 결과 없음", status_code=422)
    return result

# router.py — no try/except; propagates automatically
@router.post("/voice")
async def voice_pipeline(audio: UploadFile, user_id: str = Depends(get_current_user)):
    text = await stt_service.speech_to_text(await audio.read())
    return ApiResponse(success=True, data={"text": text}, message="인식 완료")

# main.py — AppError handler only; STTError → VoiceServiceError → AppError 체인으로 자동 처리
@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(exc.status_code,
        {"success": False, "data": None, "message": exc.message, "code": exc.code})
```

> FastAPI 내부 오류(Pydantic 422)는 `RequestValidationError` 핸들러로 별도 처리한다.

### 8.4 Anti-patterns

```python
# ❌ try/except in router.py — exception doesn't reach main.py
@router.post("/verify")
async def verify(audio: UploadFile):
    try:
        ...
    except AppError as e:
        return ApiResponse(success=False, code=e.code)   # ← pattern violation

# ❌ Swallowing exception as None — cause is hidden
async def get_user(user_id: str):
    try:
        return db.query(User).filter_by(user_id=user_id).first()
    except Exception:
        return None
```

---

## 9. Frontend Error Handling (TypeScript)

### 9.1 Architecture Overview

음성 파이프라인(`POST /api/voice`)이 백엔드 `AppError`를 TTS 오디오로 변환해 반환하므로, **프론트엔드는 서버 에러 코드를 TTS 메시지로 변환할 필요가 없다.** `utils/errorHandler.ts`는 백엔드에 도달하지 못하는 **순수 클라이언트 오류**만 관리한다.

| 계층 | 파일 | 책임 |
|------|------|------|
| 클라이언트 오류 | `utils/errorHandler.ts` | 마이크·네트워크 등 클라이언트 전용 코드 → TTS 메시지 |
| HTTP 오류 메시지 추출 | `utils/errorHandler.ts` | axios 응답에서 `message` 추출 |
| 클라이언트 오류 리포팅 | `services/errorReportService.ts` | 분류된 오류를 `POST /api/client-errors/` 로 전송 |

### 9.2 `utils/errorHandler.ts`

```typescript
// ── 클라이언트 전용 코드 → 메시지 ──────────────────────────────────────────
const CLIENT_ONLY_ERRORS: Record<string, string> = {
  MICROPHONE_PERMISSION_DENIED: '마이크 권한이 필요합니다.',
  NETWORK_ERROR:                '인터넷 연결을 확인해 주세요.',
  TTS_SERVICE_UNAVAILABLE:      '음성 서비스에 문제가 있습니다.',
  VOICE_PROCESSING_ERROR:       '음성 처리 중 오류가 발생했습니다.',
};

export const FALLBACK_MESSAGE = '오류가 발생했습니다. 잠시 후 다시 시도해 주세요.';

/** 클라이언트 전용 코드 → TTS 메시지 (음성 훅, useVoiceInput 등에서 사용) */
export function getClientErrorMessage(code: string): string {
  return CLIENT_ONLY_ERRORS[code] ?? FALLBACK_MESSAGE;
}

/** axios 오류 / AppError HTTP 응답에서 message 문자열을 추출. 없으면 FALLBACK */
export function extractApiErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    if (!err.response) return CLIENT_ONLY_ERRORS.NETWORK_ERROR;
    return (err.response.data as { message?: string })?.message ?? FALLBACK_MESSAGE;
  }
  return FALLBACK_MESSAGE;
}

/** @deprecated 신규 코드는 extractApiErrorMessage / getClientErrorMessage 사용 */
export const getTtsMessage = (code?: string): string =>
  (code && CLIENT_ONLY_ERRORS[code]) ?? FALLBACK_MESSAGE;
```

### 9.3 `services/errorReportService.ts`

네트워크·HTTP 오류를 분류해 서버로 수집한다. 음성 훅이나 서비스 레이어 `catch` 블록에서 호출한다.

```typescript
// ✅ axios 오류 분류 후 서버 리포팅
import { reportClientError } from '@/services/errorReportService';

try {
  await voiceService.sendAudio(blob);
} catch (err) {
  const msg = extractApiErrorMessage(err);
  speakText(msg);
  await reportClientError('voice', err);  // 분류·리포팅은 errorReportService가 처리
}
```

### 9.4 TTS 출력 — `utils/ttsManager.ts`

모든 음성 출력은 `speakText()`를 통한다. 직접 `Speech.speak()`를 호출하지 않는다.

```typescript
import { speakText } from '@/utils/ttsManager';

// ✅ ttsManager 경유 — 언어·속도 자동 적용
speakText('마이크 권한이 필요합니다.');

// ❌ 직접 호출 — 사용자 속도 설정 무시됨
Speech.speak('마이크 권한이 필요합니다.', { language: 'ko-KR' });
```

### 9.5 Decision Guide

| 상황 | 처리 |
|------|------|
| 음성 파이프라인 오류 (백엔드 AppError) | 백엔드가 TTS 오디오로 변환해 반환 — 프론트 처리 불필요 |
| 마이크 권한 거부 | `getClientErrorMessage('MICROPHONE_PERMISSION_DENIED')` |
| 네트워크 오류 (응답 없음) | `extractApiErrorMessage(err)` → `NETWORK_ERROR` 문구 |
| axios HTTP 오류 응답 | `extractApiErrorMessage(err)` → 서버 `message` 추출 |
| 오류 서버 수집 | `reportClientError(feature, err)` |
| 화면 이동 등 흐름 제어 | 화면 컴포넌트가 직접 처리 — `errorHandler.ts`에 추가 금지 |

---

## 10. Mutable Default Arguments (Python)

Python evaluates default values **once at definition time**. Mutable defaults are shared across all calls.

```python
# ❌ Bug — all calls share the same list
def add_voice_log(user_id: int, logs: list = []):
    logs.append(user_id)
    return logs

# ✅ Use None, create inside
def add_voice_log(user_id: int, logs: list | None = None):
    if logs is None:
        logs = []
    logs.append(user_id)
    return logs
```

---

## 11. Structured Logging (Python)

### 11.1 Setup

`core/logging_config.py`의 `setup_logging()`이 루트 로거를 JSON 포맷으로 교체한다. `main.py` 최상단에서 가장 먼저 호출해야 한다.

출력 JSON 필드: `timestamp` (KST ISO-8601), `level`, `logger`, `request_id`, `message`, `event`, (추가 `extra` 키).

### 11.2 Pattern

```python
import logging
logger = logging.getLogger(__name__)

# ✅ 구조화 로그 — event 키를 고정하고 나머지를 extra로 전달
logger.info(
    "transfer_executed",
    extra={
        "event": "transfer_executed",
        "user_id": user_id,
        "amount": amount,
        "status": "success",
    },
)

logger.error(
    "transfer_executed",
    extra={
        "event": "transfer_executed",
        "user_id": user_id,
        "status": "failed",
        "error": str(e),
    },
)

# ❌ 비구조화 문자열 — 집계·검색 불가
logger.info(f"이체 성공: user={user_id} amount={amount}")
```

### 11.3 Rules

| Rule | Detail |
|------|--------|
| `event` 키 필수 | `extra={"event": "snake_case_event_name", ...}` 형식 준수 |
| `logger.exception()` 사용 | `except` 블록에서 스택트레이스 자동 첨부 |
| 민감 정보 제외 | 계좌번호·PIN·토큰은 로그에 포함하지 않는다 |
| `request_id` 자동 주입 | `_RequestIdFilter`가 모든 레코드에 주입 — 별도 전달 불필요 |

---

## 12. Client Error Reporting (TypeScript)

프론트엔드에서 발생한 네트워크·HTTP 오류를 `POST /api/client-errors/`로 수집한다. 분류 로직은 `services/errorReportService.ts`가 담당한다.

```typescript
// services/errorReportService.ts 내부 분류 기준
// - ECONNABORTED / "timeout" 포함 → 'timeout'
// - 응답 없음                       → 'network'
// - status >= 500                   → 'http_5xx'
// - status >= 400                   → 'http_4xx'
// - 그 외                           → 'unknown'

// ✅ 서비스/훅 catch 블록에서 단순 호출
import { reportClientError } from '@/services/errorReportService';

try {
  await assetService.getSummary();
} catch (err) {
  speakText(extractApiErrorMessage(err));
  await reportClientError('asset', err);
}
```

규칙:
- `reportClientError` 실패는 무시한다 (무한 루프 방지를 위해 내부에서 catch).
- 미인증 상태(`token` 없음)에서는 호출을 생략한다.
- 화면 단위로 `feature` 이름을 명시한다 (`'voice'`, `'asset'`, `'transfer'` 등).
