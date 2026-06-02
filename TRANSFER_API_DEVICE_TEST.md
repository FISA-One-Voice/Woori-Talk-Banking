## 실기기(폰)에서 송금 API 테스트 (Mac / Windows)

### 핵심 요약

- **폰에서 `127.0.0.1` = 폰 자기 자신**이라서 백엔드에 절대 안 붙습니다.
- 백엔드는 **`0.0.0.0:8000`** 으로 띄우고, 앱의 `API Base URL`은 **PC의 LAN IP**로 설정하세요.

---

### 1) PC LAN IP 확인

#### Mac

```bash
ipconfig getifaddr en0
```

#### Windows (PowerShell)

```powershell
ipconfig
```

출력에서 **IPv4 주소**를 찾습니다. 예: `172.21.27.98`

---

### 2) 백엔드 실행 + 시드

> 백엔드 venv(3.11) 사용 기준.

#### Mac / Windows 공통

```bash
cd backend
CRYPTO_NOOP=true python tests/seed_transfer_swagger.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

### 3) 폰에서 헬스 체크

Safari/Chrome에서 아래 접속:

- `http://<PC_LAN_IP>:8000/health`

예) `http://172.21.27.98:8000/health` → **200** 이면 OK

> 오타 주의: `/heath`가 아니라 **`/health`**

---

### 4) 앱에서 송금 API 테스트 화면 실행

1. Expo로 앱 실행
2. 앱에서 `/dev` → **송금 API 테스트**
3. 화면의 `API Base URL`을 아래로 설정:
   - `http://<PC_LAN_IP>:8000`

---

### 5) 기대 결과 (4개)

- ① `recipientId` → 200, `txId`
- ② `recipientPhone`(가입) → 200
- ② `recipientPhone`(미가입) → `TRANSFER_RECIPIENT_NOT_FOUND`
- ③ `toAccountNumber` 직접입력 → 200, `recipientId: null`

---

### 자주 나는 문제

- **`NETWORK_ERROR` + 백엔드 로그 없음**: 대부분 `API Base URL`이 `127.0.0.1:8000`이거나, 백엔드가 `127.0.0.1`로만 바인딩된 경우입니다.

