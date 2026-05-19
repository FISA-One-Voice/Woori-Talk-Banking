# 개발 환경 초기 세팅 가이드


---

## Frontend 세팅

### 1. nvm 설치

nvm은 Node.js 버전을 프로젝트별로 고정해주는 도구입니다.

**Mac**

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
```

설치 후 터미널을 재시작하거나 아래 명령어로 즉시 적용합니다.

```bash
source ~/.zshrc
```

**Windows**

[nvm-windows 릴리즈 페이지](https://github.com/coreybutler/nvm-windows/releases)에서 `nvm-setup.exe` 다운로드 후 실행합니다.
설치 완료 후 **새 PowerShell 창**을 열어야 nvm 명령어가 인식됩니다.

---

### 2. Node.js 설치 및 버전 고정

```bash
# .nvmrc에 명시된 버전 자동 설치 및 적용
cd frontend
nvm install   # .nvmrc 읽어서 24.13.1 설치
nvm use       # 해당 버전으로 전환
```

> `.nvmrc` 파일은 저장소에 포함되어 있습니다. 별도로 만들 필요 없습니다.
> 팀원 간 Node 버전을 맞추기 위해 커밋되어 있습니다.

설치 확인:

```bash
node --version   # v24.13.1
npm --version    # 11.x.x
```

---

### 3. 패키지 설치 및 앱 실행

```bash
npm install
npx expo start
```

Expo Go 앱(모바일)에서 QR 코드를 찍으면 바로 확인할 수 있습니다.

---

## Backend 세팅

### 1. Python 3.11 설치

**Mac**

```bash
brew install python@3.11
```

설치 확인:

```bash
python3.11 --version   # Python 3.11.x
```

**Windows**

[Python 공식 사이트](https://www.python.org/downloads/release/python-3119/)에서
`Windows installer (64-bit)` 다운로드 후 실행합니다.

설치 시 **"Add Python to PATH"** 체크박스를 반드시 선택해야 합니다.

설치 확인 (PowerShell):

```powershell
py -3.11 --version   # Python 3.11.x
```

---

### 2. 가상환경(.venv) 생성 및 활성화

가상환경은 프로젝트마다 패키지를 독립적으로 관리하기 위한 격리 공간입니다.
`.venv` 폴더는 `.gitignore`에 포함되어 있어 저장소에 올라가지 않습니다.
팀원 각자 아래 명령어로 직접 생성해야 합니다.

**Mac**

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell)**

```powershell
cd backend
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
```

> PowerShell에서 "스크립트 실행이 차단됨" 오류가 나면 아래 명령어 먼저 실행합니다.
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

활성화 확인 — 터미널 앞에 `(.venv)` 표시가 나타나면 정상입니다.

```
(.venv) backend $
```

---

### 3. 패키지 설치

```bash
pip install -r requirements.txt
```
