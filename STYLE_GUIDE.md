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

### 5.1 Voice & NLU

| 에러 코드 | 설명 |
|-----------|------|
| `VOICE_AUTH_FAILED` | 음성 인증 실패 (종합) |
| `VOICE_SPOOF_DETECTED` | Anti-spoofing 감지 |
| `STT_FAILED` | STT 변환 자체 실패 (타임아웃 외) |
| `VOICE_PROFILE_ALREADY_EXISTS` | 음성 프로필 중복 등록 시도 — `unique` 제약 위반 (user_id 1:1) |
| `VOICE_AUDIO_TOO_LONG` | 음성 파일 길이 초과 — CLOVA STT 60초 제한 |
| `VOICE_AUDIO_TOO_LARGE` | 음성 파일 용량 초과 — STT API 호출 가능 최대 10MB 제한 |
| `VOICE_AUDIO_INVALID_FORMAT` | 지원하지 않는 오디오 포맷 |
| `VOICE_VECTOR_EXTRACT_FAILED` | 음성 벡터(embedding) 추출 실패 — pgvector 저장 전 단계 오류 |
| `ASV_CONFIDENCE_LOW` | ASV confidence 기준 미달 — confidence < 0.66 - 성능평가 시 최적값. 실제로 해보면서 수정 가능 (`VOICE_AUTH_FAILED`와 구분) |
| `NLU_INTENT_UNRECOGNIZED` | 음성 발화 "의도 인식" 실패 → 재발화 안내 — `/nlu/parse` 422 |

### 5.2 Account

| 에러 코드 | 설명 |
|-----------|------|
| `ACCOUNT_NOT_FOUND` | 계좌를 찾을 수 없음 |
| `ACCOUNT_INSUFFICIENT_BALANCE` | 잔액 부족 — `balance >= 0` CHECK 위반 방지 |
| `ACCOUNT_ALIAS_DUPLICATE` | 계좌 별칭 중복 — 음성 발화 매칭 충돌 방지 |

### 5.3 Transfer & Transaction

| 에러 코드 | 설명 |
|-----------|------|
| `TRANSFER_AMOUNT_INVALID` | 송금액 0 이하 — `amount > 0` CHECK 위반 |
| `TRANSFER_RECIPIENT_NOT_FOUND` | 수취인 계좌 조회 실패 — 미등록 수취인 실시간 조회 실패 포함 |
| `TRANSFER_SESSION_INVALID` | sessionToken 위변조 또는 미존재 |
| `TRANSFER_IDEMPOTENCY_CONFLICT` | 멱등키 중복 — 동일 송금 재요청 방지 |
| `TX_NOT_FOUND` | 거래 내역을 찾을 수 없음 |
| `TX_ALREADY_PROCESSED` | 이미 완료/실패 처리된 거래 — `status: completed / failed` 재처리 시도 |

### 5.4 Standing Order

| 에러 코드 | 설명 |
|-----------|------|
| `AUTO_ORDER_SCHEDULE_INVALID` | 스케줄 값 오류 — `scheduled_day` (1~31) / `scheduled_dow` (0~6) 범위 위반 |
| `AUTO_ORDER_TERMS_NOT_AGREED` | 자동이체 약관 미동의 — `terms_agreed_at` 누락 |
| `AUTO_ORDER_WITHDRAWAL_PASSWORD_INVALID` | 출금 계좌 비밀번호 불일치 — `password_hash` bcrypt 검증 실패 |
| `AUTO_ORDER_EXECUTION_FAILED` | 자동이체 실행 중 오류 — 잔액 부족 등 실행 시점 실패 |
| `AUTO_ORDER_INVALID_MONTH_END` | 29~31일 등록 시 말일 처리 예외 |

### 5.5 Recipient

| 에러 코드 | 설명 |
|-----------|------|
| `RECIPIENT_NOT_FOUND` | 등록 수취인을 찾을 수 없음 |
| `RECIPIENT_ALIAS_DUPLICATE` | 수취인 별칭 중복 — 음성 발화 매칭 충돌 ("엄마" 중복 등) |
| `CONTACT_AMBIGUOUS` | 동명이인 다중 매칭 → TTS 목록 안내 — `/contacts/match` |

### 5.6 User & Authentication

| 에러 코드 | 설명 |
|-----------|------|
| `UNAUTHORIZED` | 인증되지 않은 요청 |
| `USER_NOT_FOUND` | 사용자를 찾을 수 없음 |
| `USER_PHONE_DUPLICATE` | 이미 가입된 전화번호 — `PUT /users/{userId}` 409 |
| `TOKEN_INVALID` | 토큰 위변조 또는 유효하지 않음 |
| `TTS_SPEED_OUT_OF_RANGE` | TTS 속도 범위 초과 — `tts_speed` CHECK (0.25~4.0) 위반 |

### 5.7 Common

| 에러 코드 | 설명 |
|-----------|------|
| `INTERNAL_ERROR` | 서버 내부 오류 |
| `INVALID_REQUEST` | 요청 파라미터 형식 오류 — Pydantic 검증 실패 |
| `RESOURCE_NOT_FOUND` | 요청한 리소스 없음 (범용 404) |
| `FORBIDDEN` | 권한 없음 — 인증됐으나 접근 불가 (403) |
| `RATE_LIMIT_EXCEEDED` | API 요청 횟수 초과 |
| `SERVICE_UNAVAILABLE` | 외부 서비스 장애 — CLOVA |

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

All domain errors inherit from `AppError`. One subclass per feature module — matching the team's ownership model. `main.py` handles only the parent class; all subclasses are caught automatically.

```python
# core/exception.py
class AppError(Exception):
    def __init__(self, code: str, status_code: int = 400, message: str = ""):
        self.code, self.status_code, self.message = code, status_code, message

# One class per feature — mirrors features/ directory structure
class AuthError(AppError): pass          # features/auth/
class BalanceError(AppError): pass       # features/balance/
class TransferError(AppError): pass      # features/transfer/
class AutoTransferError(AppError): pass  # features/auto_transfer/
class HistoryError(AppError): pass       # features/history/
class EventError(AppError): pass         # features/event/
class ChatbotError(AppError): pass       # features/chatbot/
class VoiceError(AppError): pass         # features/voice/
```

> Shared utilities (`shared/audit.py`, `shared/stt.py`) must not raise feature-specific errors.
> Let the exception propagate; the calling service wraps it in its own error class.

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
async def verify_speaker(audio_path: str, user_id: int) -> dict:
    try:
        similarity = await compare_voice_vector(audio_path, user_id)
    except Exception:
        raise VoiceAuthError("VOICE_VECTOR_EXTRACT_FAILED", status_code=500)

    if similarity < 0.66:
        raise VoiceAuthError("ASV_CONFIDENCE_LOW", status_code=401)
    return {"similarity": similarity}

# router.py — no try/except; propagates automatically
@router.post("/verify")
async def verify(audio: UploadFile, user_id: str = Depends(get_current_user)):
    result = await service.verify_speaker(audio.filename, user_id)
    return ApiResponse(success=True, data=result, message="인증 완료")

# main.py — AppError handler + fallback
@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(exc.status_code,
        {"success": False, "data": None, "message": exc.message, "code": exc.code})

@app.exception_handler(Exception)
async def unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(500,
        {"success": False, "data": None, "message": "서버 내부 오류", "code": "INTERNAL_ERROR"})
```

> FastAPI internal errors (Pydantic 422, OAuth2 401) still use `HTTPException`, so add
> `@app.exception_handler(HTTPException)` if needed.

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

The two layers are **parallel** — API errors don't reach `ErrorBoundary`, and render crashes don't reach `errorHandler.ts`.

| Layer | File | Responsibility |
|------|------|------|
| API errors | `utils/errorHandler.ts` | Convert server `code` → TTS message |
| Render crashes | `components/ErrorBoundary.tsx` | Catch exceptions thrown during React render |

### 9.1 `utils/errorHandler.ts`

Corresponds to `main.py`'s `@app.exception_handler`. All code→message mappings live here only.

```typescript
// utils/errorHandler.ts
const MESSAGES: Record<string, string> = {
  ASV_CONFIDENCE_LOW:           '목소리가 잘 인식되지 않았습니다. 다시 말씀해 주세요.',
  ACCOUNT_INSUFFICIENT_BALANCE: '잔액이 부족합니다.',
  UNAUTHORIZED:                 '로그인이 필요합니다.',
  INTERNAL_ERROR:               '서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
  // … all error codes from §5
};
const FALLBACK = '오류가 발생했습니다. 잠시 후 다시 시도해 주세요.';
export const getTtsMessage = (code?: string) => (code && MESSAGES[code]) ?? FALLBACK;

// ✅ Screen — delegate message lookup, own flow control
if (!response.data.success) {
  tts(getTtsMessage(response.data.code));
  if (response.data.code === 'UNAUTHORIZED') router.replace('/auth/login');
}

// ❌ String literal in screen
tts('목소리가 잘 인식되지 않았습니다. 다시 말씀해 주세요.');
// ❌ Duplicate switch in every screen
switch (response.data.code) { case 'ASV_CONFIDENCE_LOW': tts('…'); }
```

### 9.2 `components/ErrorBoundary.tsx`

For render-time crashes only — do not handle API errors here.

```tsx
// components/ErrorBoundary.tsx
export default class ErrorBoundary extends React.Component<
  { children: React.ReactNode }, { hasError: boolean }
> {
  state = { hasError: false };
  static getDerivedStateFromError = () => ({ hasError: true });
  componentDidCatch = (e: Error) => console.error('[ErrorBoundary]', e); // TODO: Sentry

  render() {
    if (this.state.hasError)
      return (
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
          <Text>예기치 않은 오류가 발생했습니다.</Text>
          <Pressable onPress={() => this.setState({ hasError: false })}>
            <Text>다시 시도</Text>
          </Pressable>
        </View>
      );
    return this.props.children;
  }
}

// app/_layout.tsx
export default function RootLayout() {
  return <ErrorBoundary><Stack /></ErrorBoundary>;
}
```

### 9.3 Decision Guide

| Situation | Handle In |
|------|----------|
| Server returns `{ success: false, code: "..." }` | `getTtsMessage(code)` |
| Network error (no response) | `getTtsMessage('NETWORK_ERROR')` |
| Component crash during render | `ErrorBoundary.tsx` |
| Flow control after API error (navigate, retry) | Screen component — don't add to `errorHandler.ts` |

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
