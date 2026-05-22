# 코드 스타일 가이드

> React (TypeScript) + FastAPI (Python) 기준
>
> Python 규칙은 [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html) 기반

---


## 1. 들여쓰기

| 영역 | 규칙 |
|------|------|
| Frontend (TypeScript) | 스페이스 2칸 |
| Backend (Python) | 스페이스 4칸 (PEP8 표준) |

---

## 2. 명명규칙 

### 2.1 명명규칙 종류 

| 케이스 | 규칙 | 예시 |
|--------|------|------|
| `camelCase` | 첫 단어 소문자, 이후 단어 첫 글자 대문자 | `userName`, `fetchUserData` |
| `PascalCase` | 모든 단어 첫 글자 대문자 | `UserProfile`, `VoiceAuthModal` |
| `snake_case` | 모든 소문자, 단어 사이 언더스코어 | `user_id`, `get_voice_vector` |
| `UPPER_SNAKE_CASE` | 모든 대문자, 단어 사이 언더스코어 | `MAX_FILE_SIZE`, `API_BASE_URL` |
| `kebab-case` | 모든 소문자, 단어 사이 하이픈 | `voice-auth-button`, `/voice-auth` |


### 2.2 명명규칙

#### Frontend (TypeScript)

| 대상 | 방식 | 예시 |
|------|------|------|
| 변수 / 함수 | camelCase | `userName`, `fetchUserData()` |
| 컴포넌트 | PascalCase | `VoiceAuthModal`, `TransferForm` |
| 타입 / 인터페이스 | PascalCase | `UserProfile`, `ApiResponse` |
| 상수 | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT`, `API_BASE_URL` |
| CSS 클래스 | kebab-case | `voice-auth-button`, `transfer-form` |
| 파일명 (컴포넌트) | PascalCase | `VoiceAuthModal.tsx` |
| 파일명 (유틸/훅) | camelCase | `useVoiceAuth.ts`, `formatCurrency.ts` |

#### Backend (Python)

| 대상 | 방식 | 예시 |
|------|------|------|
| 변수 / 함수 | snake_case | `user_id`, `get_voice_vector()` |
| 클래스 | PascalCase | `UserService`, `VoiceAuthRequest` |
| 상수 | UPPER_SNAKE_CASE | `MAX_FILE_SIZE`, `STT_TIMEOUT` |
| 파일명 | snake_case | `voice_auth.py`, `user_router.py` |
| API 라우터 prefix | kebab-case | `/voice-auth`, `/asset-inquiry` |

---

## 3. 함수 길이 제한

- **최대 50줄** 권장, **80줄** 초과 금지
- 80줄이 넘으면 기능 단위로 함수 분리
- 한 함수는 **하나의 역할**만 담당

```python
# ❌ 나쁜 예 - 한 함수에서 너무 많은 일을 함
async def handle_voice_auth(audio_file):
    # 파일 저장 로직 20줄
    # STT 변환 로직 20줄
    # 음성 벡터 비교 로직 20줄
    # DB 저장 로직 20줄  ← 80줄 초과

# ✅ 좋은 예 - 역할별로 분리
async def handle_voice_auth(audio_file):
    saved_path = await save_audio_file(audio_file)
    transcript = await convert_to_text(saved_path)
    is_verified = await compare_voice_vector(saved_path)
    await save_auth_log(is_verified)
    return is_verified
```

---

## 4. 주석 규칙

### 4.1 주석을 달아야 하는 경우
- 비즈니스 로직이 복잡한 경우 
- 외부 API 연동 시 주의사항이 있는 경우
- 임시 처리 코드 (`# TODO:`, `# FIXME:`)
- 왜 이렇게 짰는지 이유가 필요한 경우
- 실행 순서가 중요한 코드 (순서를 바꾸면 버그가 생기는 경우)
- 의도적으로 예외처리를 생략한 경우

### 4.2 주석을 달지 않아도 되는 경우
- 함수명/변수명만 봐도 의도가 명확한 경우
- 단순 CRUD 로직

```python
# ✅ 좋은 주석 - 이유를 설명함
# NAVER CLOVA STT는 최대 60초 음성만 지원하므로 사전에 길이 검증
if audio_duration > 60:
    raise ValueError("음성은 60초를 초과할 수 없습니다.")

# ❌ 나쁜 주석 - 코드를 그냥 읽어줌
# user_id를 가져옴
user_id = get_user_id()
```

```typescript
// TODO: 카드 내역 TTS 알림 기능 구현 예정 (2024 Q2)
// FIXME: 음성 녹음 중 백그라운드 전환 시 녹음 끊기는 이슈
```

---

## 5. API 응답 형식

모든 API는 아래 형식을 통일해서 사용합니다.

### 성공 응답

```json
{
  "success": true,
  "data": {
    // 실제 응답 데이터
  },
  "message": "요청이 성공적으로 처리되었습니다."
}
```

### 실패 응답

```json
{
  "success": false,
  "data": null,
  "message": "음성 인증에 실패했습니다.",
  "error_code": "VOICE_AUTH_FAILED"
}
```


### 에러 코드 목록
 
> 코드 스타일 가이드 연계 문서  
> DB 다이어그램 + API 명세서 기준으로 도메인별 분류  
> `신규` 표시 = 기존 목록에서 추가된 항목
 
 
 
### 5.1 음성 · NLU 에러 코드 목록
 
| 에러 코드 | 설명 | 
|-----------|------|
| `VOICE_AUTH_FAILED` | 음성 인증 실패 (종합) 
| `VOICE_SPOOF_DETECTED` | Anti-spoofing 감지 |
| `STT_FAILED` | STT 변환 자체 실패 (타임아웃 외) |
| `VOICE_PROFILE_ALREADY_EXISTS` | 음성 프로필 중복 등록 시도 — `unique` 제약 위반 (user_id 1:1) | 
| `VOICE_AUDIO_TOO_LONG` | 음성 파일 길이 초과 — CLOVA STT 60초 제한 |
| `VOICE_AUDIO_TOO_LARGE` | 음성 파일 용량 초과 — STT API 호출 가능 최대 10MB 제한 |
| `VOICE_AUDIO_INVALID_FORMAT` | 지원하지 않는 오디오 포맷 | 
| `VOICE_VECTOR_EXTRACT_FAILED` | 음성 벡터(embedding) 추출 실패 — pgvector 저장 전 단계 오류 | 
| `ASV_CONFIDENCE_LOW` | ASV confidence 기준 미달 — confidence < 0.66 - 성능평가 시 최적값. 실제로 해보면서 수정 가능 (`VOICE_AUTH_FAILED`와 구분) | 
| `NLU_INTENT_UNRECOGNIZED` | 음성 발화 "의도 인식" 실패 → 재발화 안내 — `/nlu/parse` 422 | 


 
 
### 5.2. 계좌 에러 코드 목록
 
| 에러 코드 | 설명 | 
|-----------|------|
| `ACCOUNT_NOT_FOUND` | 계좌를 찾을 수 없음 |
| `ACCOUNT_INSUFFICIENT_BALANCE` | 잔액 부족 — `balance >= 0` CHECK 위반 방지 | 
| `ACCOUNT_ALIAS_DUPLICATE` | 계좌 별칭 중복 — 음성 발화 매칭 충돌 방지 | 
 

 
### 5.3 송금 · 거래 에러 코드 목록
 
| 에러 코드 | 설명 | 
|-----------|------|
| `TRANSFER_AMOUNT_INVALID` | 송금액 0 이하 — `amount > 0` CHECK 위반 | 
| `TRANSFER_RECIPIENT_NOT_FOUND` | 수취인 계좌 조회 실패 — 미등록 수취인 실시간 조회 실패 포함 | 
| `TRANSFER_SESSION_INVALID` | sessionToken 위변조 또는 미존재 |
| `TRANSFER_IDEMPOTENCY_CONFLICT` | 멱등키 중복 — 동일 송금 재요청 방지 | 
| `TX_NOT_FOUND` | 거래 내역을 찾을 수 없음 |
| `TX_ALREADY_PROCESSED` | 이미 완료/실패 처리된 거래 — `status: completed / failed` 재처리 시도 | 
 

### 5.4 자동이체 에러 코드 목록
 
| 에러 코드 | 설명 |
|-----------|------|
| `AUTO_ORDER_SCHEDULE_INVALID` | 스케줄 값 오류 — `scheduled_day` (1~31) / `scheduled_dow` (0~6) 범위 위반 | 
| `AUTO_ORDER_TERMS_NOT_AGREED` | 자동이체 약관 미동의 — `terms_agreed_at` 누락 | 
| `AUTO_ORDER_WITHDRAWAL_PASSWORD_INVALID` | 출금 계좌 비밀번호 불일치 — `password_hash` bcrypt 검증 실패 | 
| `AUTO_ORDER_EXECUTION_FAILED` | 자동이체 실행 중 오류 — 잔액 부족 등 실행 시점 실패 | 
| `AUTO_ORDER_INVALID_MONTH_END` | 29~31일 등록 시 말일 처리 예외 |
 

 
### 5.5 수취인 에러 코드 목록
 
| 에러 코드 | 설명 | 
|-----------|------|
| `RECIPIENT_NOT_FOUND` | 등록 수취인을 찾을 수 없음 | 
| `RECIPIENT_ALIAS_DUPLICATE` | 수취인 별칭 중복 — 음성 발화 매칭 충돌 ("엄마" 중복 등) | 
| `CONTACT_AMBIGUOUS` | 동명이인 다중 매칭 → TTS 목록 안내 — `/contacts/match` | 
 

 
### 5.6 회원 · 인증 에러 코드 목록
 
| 에러 코드 | 설명 | 
|-----------|------|
| `UNAUTHORIZED` | 인증되지 않은 요청 | 
| `USER_NOT_FOUND` | 사용자를 찾을 수 없음 |
| `USER_PHONE_DUPLICATE` | 이미 가입된 전화번호 — `PUT /users/{userId}` 409 | 
| `TOKEN_INVALID` | 토큰 위변조 또는 유효하지 않음 | 
| `TTS_SPEED_OUT_OF_RANGE` | TTS 속도 범위 초과  — `tts_speed` CHECK (0.25~4.0) 위반 | 
 


### 5.7 공통 에러 코드 목록
 
| 에러 코드 | 설명 | 
|-----------|------|
| `INTERNAL_ERROR` | 서버 내부 오류 | 
| `INVALID_REQUEST` | 요청 파라미터 형식 오류 — Pydantic 검증 실패 |
| `RESOURCE_NOT_FOUND` | 요청한 리소스 없음 (범용 404) |
| `FORBIDDEN` | 권한 없음 — 인증됐으나 접근 불가 (403) | 
| `RATE_LIMIT_EXCEEDED` | API 요청 횟수 초과 | 
| `SERVICE_UNAVAILABLE` | 외부 서비스 장애 — CLOVA | 
 
---
 

## 6. API 응답 작성 가이드 (FastAPI)

### 6.1 성공 응답
```python
# ✅ 항상 success=True, data에 결과, message에 완료 문구
return ApiResponse(success=True, data=result, message="처리 완료")
```

### 6.2 실패 응답
```python
# ✅ success=False, message는 사람이 읽는 설명, error_code는 클라이언트 분기용
return ApiResponse(
    success=False,
    message="ASV confidence 기준 미달",
    error_code="ASV_CONFIDENCE_LOW"
)

# ❌ error_code 없이 message만 내리면 클라이언트가 분기 불가
return ApiResponse(success=False, message="인증 실패")
```

### 6.3 규칙
- `message` — 사람이 읽는 설명. 로그/디버그용
- `error_code` — 클라이언트 분기용. 에러 코드 목록에 정의된 값만 사용
- 실패 응답에 `error_code` 누락 금지



### 6.4 에러 응답 처리 가이드 (Frontend)

### 기본 구조
```typescript
// ✅ error_code 기준으로 switch 분기
const response = await api.post<ApiResponse<VoiceAuthResult>>('/voice/verify-speaker');
if (!response.data.success) {
  switch (response.data.error_code) {
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

### 6.5 규칙
- `error_code` 기준으로 분기. `message` 문자열로 비교하지 않기
- `default` 케이스 반드시 작성 — 예상 못한 에러 대비
- TTS 문구는 사용자 친화적으로 — 기술 용어 노출 금지 (`"ASV 실패"` 같은 문구 사용 금지)


---

## 7. 타입 힌트 (Python) 
Public API 함수에는 **반드시** 타입 힌트를 달아야 합니다.  
FastAPI 라우터 함수는 타입 힌트 없으면 동작 자체가 안 되므로 자연스럽게 따라가게 되고,  
서비스 / 유틸 함수도 최소한 인자와 반환값 타입은 명시합니다.
### 7.1 타입 힌트 작성 가이드


| 대상 | 필수 여부 |
|------|-----------|
| Public API / 서비스 / 유틸 함수 | ✅ 필수 |
| FastAPI 라우터 | ✅ 필수 (없으면 동작 안 함) |
| 내부 헬퍼 / 간단한 람다 | 🔶 권장 |
| 테스트 코드 | 🔶 선택 |


### 7.2  체크리스트

함수 작성할 때 아래 순서로 확인하세요.

#### 1. 인자 타입 달았나?

```python
# ❌
def process(user_id, amount):

# ✅
def process(user_id: int, amount: float):
```

#### 2. 반환 타입 달았나?

```python
# ❌
def get_user(user_id: int):

# ✅
def get_user(user_id: int) -> UserSchema:
```

#### 3. None 가능성 표시했나?

```python
# ❌ None 반환 가능한데 숨김
def find_user(user_id: int) -> UserSchema:

# ✅
def find_user(user_id: int) -> UserSchema | None:
```

#### 4. 파라미터 3개 이상이면 줄바꿈했나?

```python
# ❌
async def transfer_money(sender_id: int, receiver_id: int, amount: float, memo: str | None = None) -> TransferResult:

# ✅
async def transfer_money(
    sender_id: int,
    receiver_id: int,
    amount: float,
    memo: str | None = None,
) -> TransferResult:
```



#### 7.3 자주 쓰는 타입 패턴 모음

```python
# 없을 수도 있는 값
value: str | None = None

# 리스트 / 딕셔너리
items: list[UserSchema]
config: dict[str, int]

# 비동기 함수
async def fetch() -> list[TransactionSchema]: ...

# 아무것도 반환 안 할 때
def log_event(event: str) -> None: ...

# 여러 타입 가능
def parse(value: int | str) -> str: ...
```


#### ⚠️ 주의

```python
-> Any       # 타입 포기 선언, 꼭 필요한 경우만
-> object    # 너무 추상적
# 반환 타입 생략  # None인지 뭔지 알 수가 없음
```

---

## 8. Docstring (Python)  


### 8.1 Docstring 작성 가이드


| 대상 | 여부 | 이유 |
|------|------|------|
| 라우터 함수 | ✅ 필수 | API 진입점 — 동작/파라미터/예외 명확히 |
| 서비스 함수 | ✅ 필수 | 비즈니스 로직 의도 설명 필요 |
| 유틸 함수 (공통) | ✅ 필수 | 재사용 시 인터페이스 파악 목적 |
| 클래스 (public) | ✅ 필수 | 역할 및 주요 속성 명시 |
| 내부 헬퍼 함수 | 🔶 권장 | 로직이 명확하면 생략 가능 |
| 단순 CRUD 함수 | 🔷 생략 가능 | 함수명으로 의도 파악 가능한 경우 |
| 테스트 함수 | 🔷 생략 가능 | 테스트 코드 자체가 명세 역할 |


### 표준 섹션 구조

```python
async def compare_voice_vector(audio_path: str, user_id: int) -> bool:
    """한 줄 요약 (마침표로 끝내기).

    # 필요할 때만 — 한 줄 요약으로 부족한 경우
    긴 설명이 필요한 경우 빈 줄 이후에 작성합니다.
    여러 줄도 가능합니다.

    Args:
        audio_path: S3에 업로드된 음성 파일 경로.
        user_id: 인증 대상 사용자 ID.

    Returns:
        인증 성공 시 True, 실패 시 False. 

    Raises:
        FileNotFoundError: 음성 파일이 S3에 없는 경우.
        VoiceAuthError: 벡터 비교 중 오류 발생 시.
    """
```


### 8.2 섹션별 작성 규칙

- **한 줄 요약** — 첫 줄에 동작을 동사로 시작, 마침표로 끝냄. `"""음성벡터를 비교합니다."""` 처럼 명확하게.
- **Args** — 타입 힌트가 있으면 타입 생략, 설명만 작성. 없으면 `name (int): 설명` 형식.
- **Returns** — `bool`처럼 타입만 쓰지 말고, 값의 의미를 설명. `None`이면 생략 가능.
- **Raises** — 함수가 명시적으로 `raise`하는 예외만 작성하여 미리 설명. 라이브러리 내부 예외는 생략.
- **긴 설명** — 복잡한 알고리즘, 외부 API 연동 주의사항, 비즈니스 규칙이 있을 때만 추가.


### 8.3 클래스 Docstring 
이 클래스가 어떤 속성을 들고 있는지 미리 알려주기

```python
class VoiceAuthService:
    """음성 인증 관련 비즈니스 로직을 처리하는 서비스.

    Attributes:
        db: 데이터베이스 세션.
        s3_client: S3 클라이언트 인스턴스.
    """
    # __init__ 에는 별도 docstring 불필요
    # (클래스 docstring에 이미 속성 설명이 있으므로)
```

### 8.4 자주 하는 실수

```python
# ❌ 타입을 그대로 반복
Returns:
    bool

# ❌ 함수명을 그대로 번역
"""compare_voice_vector 함수입니다."""

# ❌ Raises에 모든 예외 나열
Raises:
    Exception: 오류 발생 시.  # 너무 모호함


# ✅ 의미 설명
Returns:
    인증 성공 시 True, 실패 시 False.

# ✅ 동작 중심 요약
"""음성 벡터를 비교하여 인증 여부를 반환합니다."""

# ✅ 명확한 예외만
Raises:
    VoiceAuthError: 벡터 비교 중 오류 발생 시.
```

---

> 💡 **VSCode 팁** — `autoDocstring` 확장 설치하면 함수 아래에서 `"""` 입력 시 Google 스타일 골격 자동 생성됩니다.

```python
# ✅ 표준 형식
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

클래스 -> Docstring을 달고, public 속성은 `Attributes:` 섹션에 정리합니다.

```python
class VoiceAuthService:
    """음성 인증 관련 비즈니스 로직을 처리하는 서비스.

    Attributes:
        db: 데이터베이스 세션.
        s3_client: S3 클라이언트 인스턴스.
    """
```

---

## 9. 예외 처리 (Python) 
 
 
### 9.1 기본 원칙
 
- `try` 블록 안에 코드를 **최소한**으로 유지 — 범위가 넓을수록 예상 못한 예외를 삼킬 위험이 있음
- `except:` 또는 `except Exception:` 단독 사용 금지 — 구체적인 예외 타입 명시
- 커스텀 예외는 반드시 기존 예외 클래스를 상속하고, 이름은 `Error`로 끝냄

### 9.2 규칙 요약
 
| 규칙 | 설명 |
|------|------|
| `except:` 단독 금지 | 반드시 구체적인 예외 타입 명시 |
| `try` 최소화 | 실패 가능한 핵심 라인만 감쌀 것 |
| 커스텀 예외는 `Error`로 끝냄 | `VoiceAuthError`, `TransferError` 등 |
| `assert` 비즈니스 로직 사용 금지 | `if` + `raise`로 대체 |
| 에러코드는 `detail`에 담아 반환 | `{"error": "ERROR_CODE"}` 형식 통일 |
| 리소스 정리는 `finally` | 파일, 임시 데이터 등 |

### 9.3 에러 코드와 연결하는 패턴
 
```python
# ✅ 커스텀 예외 → FastAPI HTTPException → 에러코드 순서로 변환
async def verify_speaker(audio_path: str, user_id: int) -> ApiResponse:
    try:
        similarity = await compare_voice_vector(audio_path, user_id)
    except VoiceAuthError:
        raise HTTPException(
            status_code=500,
            detail={"error": "VOICE_VECTOR_EXTRACT_FAILED"},
        )
 
    if similarity < 0.66:
        # confidence < 0.66 — 성능평가 시 최적값, 실제 운용 중 수정 가능
        raise HTTPException(
            status_code=401,
            detail={"error": "ASV_CONFIDENCE_LOW"},
        )
 
    return ApiResponse(success=True, data={"similarity": similarity}, message="인증 완료")
```
---

### 10. 함수 기본값에 mutable 객체 금지 (Python)

Python 함수의 기본값은 함수 정의 시 **단 한 번만** 평가됩니다.  
리스트, 딕셔너리 등 mutable 객체를 기본값으로 쓰면 호출 간에 값이 공유되는 버그가 생깁니다.

```python
# ❌ 버그 - 모든 호출이 같은 리스트를 공유함(처음에 만든 리스트를 계속 재사용)
def add_voice_log(user_id: int, logs: list = []):
    logs.append(user_id)
    return logs

# ✅ 올바른 방법 - 기본값을 none 으로 두고, 함수 안에서 새 리스트 만들기 
def add_voice_log(user_id: int, logs: list | None = None):
    if logs is None:
        logs = []
    logs.append(user_id)
    return logs
```

---
