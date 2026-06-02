# 팀 프로젝트 협업 가이드라인

GitHub을 써본 적은 있지만 팀 협업은 처음인 분들을 위한 가이드입니다. 처음부터 끝까지 한 번 읽어두고, 작업 중에 필요한 부분을 찾아보세요.

---

## 한눈에 보기

### 역할별 권한

| 항목 | 팀 리더 | 팀원 |
| :---- | :---: | :---: |
| `main`에 직접 push | ❌ | ❌ |
| `develop`에 직접 push | ❌ | ❌ |
| `feature/` 브랜치 생성 · push | ✅ | ✅ |
| PR 생성 · 리뷰 · 승인 | ✅ | ✅ |
| PR Merge (`feature` → `develop`) | ✅ 승인 2개 충족 시 | ✅ 승인 2개 충족 시 |
| PR Merge (`develop` → `main`) | ✅ | ❌ |
| 라벨 · 마일스톤 · 저장소 설정 | ✅ | ❌ |

**핵심 규칙:** 모든 코드 변경은 PR을 통해서만 `develop`에 반영됩니다. PR은 팀원 2명의 승인이 있어야 Merge할 수 있습니다.

### 브랜치 구조

main       ── 최종 배포 버전. 버전 태그(v1.0.0)가 붙습니다.

  └── develop  ── 팀 전체의 작업이 모이는 통합 브랜치.

        ├── feature/button-component   ← 내가 작업하는 브랜치

        ├── feature/login-screen

        └── feature/card-component

`main`과 `develop`에는 직접 push할 수 없습니다. 항상 `feature/` 브랜치를 만들어 작업하고, PR을 통해 `develop`에 반영합니다.

---

## 목차

1. [처음 시작하기](#1-처음-시작하기)  
2. [매일 반복하는 작업 흐름](#2-매일-반복하는-작업-흐름)  
3. [커밋 가이드](#3-커밋-가이드)  
4. [이슈 활용법](#4-이슈-활용법)  
5. [PR 가이드](#5-pr-가이드)  
6. [코드 리뷰 가이드](#6-코드-리뷰-가이드)  
7. [칸반 보드 사용법](#7-칸반-보드-사용법)  
8. [부록: 관리자 초기 설정](#8-부록-관리자-초기-설정)

---

## 1\. 처음 시작하기

### 저장소 클론

git clone https://github.com/\[org-name\]/\[repo-name\].git

cd \[repo-name\]

니클론하면 기본적으로 `main` 브랜치에 있습니다. 작업은 항상 `develop`에서 시작하므로 아래 명령으로 이동하세요.

git switch develop

git pull origin develop   \# 항상 최신 상태로 맞추고 시작합니다

### 브랜치 이름 짓는 법

모든 작업 브랜치는 `feature/` 로 시작합니다. 이름은 작업 내용을 간결하게 표현합니다.

feature/login-screen       ✅

feature/button-component   ✅

feature/loginScreen        ❌  (카멜케이스 사용 금지)

feature/버튼               ❌  (한글 사용 금지)

login-screen               ❌  (feature/ 접두사 누락)

---

## 2\. 매일 반복하는 작업 흐름

새 작업을 시작할 때마다 아래 사이클을 반복합니다.

이슈 확인 → 브랜치 생성 → 개발 → 커밋 → PR 생성 → 리뷰 → Merge

### Step 1 — 이슈 확인

칸반 보드의 **To Do** 컬럼에서 내 이름이 담당자로 지정된 이슈를 확인합니다. 이슈 번호를 기억해 두세요. PR 작성 시 사용합니다.

### Step 2 — 브랜치 생성

`develop` 최신 상태에서 브랜치를 만듭니다.

git switch develop

git pull origin develop

git switch \-c feature/login-screen

브랜치를 만든 뒤 칸반 보드에서 이슈를 **To Do → In Progress**로 이동합니다.

### Step 3 — 개발 · 커밋

작업하면서 논리적 단위가 완성될 때마다 커밋합니다. 커밋 메시지 작성법은 [3\. 커밋 가이드](#3-커밋-가이드)를 참고하세요.

git add \-p            \# 변경 내용을 확인하며 스테이징

git commit \-m "feat(login): 로그인 폼 UI 구현"

git push origin feature/login-screen

### Step 4 — PR 생성

GitHub에서 **New pull request**를 클릭하면 PR 설명란에 템플릿이 자동으로 채워집니다. 내용을 채우고, **관련 이슈** 항목에 `Closes #이슈번호`를 반드시 작성하세요.

Coses \#12   ← 이렇게 쓰면 PR이 Merge될 때 이슈가 자동으로 닫힙니다

PR을 열면 칸반 보드에서 이슈를 **In Progress → In Review**로 이동합니다.  
Step 5 — 리뷰 · Mergel  
팀원 2명의 승인(Approve)을 받으면 Merge할 수 있습니다. 리뷰 방법은 [6\. 코드 리뷰 가이드](#6-코드-리뷰-가이드)를 참고하세요. Merge 후 브랜치는 자동으로 삭제됩니다.

---

## 3\. 커밋 가이드

### 커밋 메시지 형식

\<type\>(\<scope\>): \<subject\>

- **type**: 이 커밋이 무엇을 하는지 (아래 목록 참고)  
- **scope**: 어느 부분에 영향을 주는지 (선택. 컴포넌트명이나 모듈명)  
- **subject**: 변경 내용 요약, 50자 이내, 동사로 시작, 마침표 없이

feat(login): 로그인 폼 UI 구현

fix(auth): 토큰 만료 시 500 에러 수정

docs: README 설치 방법 추가

chore: ESLint 설정 추가

### type 목록

| type | 언제 쓰나 |
| :---- | :---- |
| `feat` | 새로운 기능을 추가할 때 |
| `fix` | 버그를 수정할 때 |
| `docs` | README, 주석 등 문서를 수정할 때 |
| `style` | 줄바꿈, 세미콜론 등 코드 동작에 영향 없는 포맷 변경 |
| `refactor` | 기능 변화 없이 코드 구조를 개선할 때 |
| `chore` | 패키지, 빌드, 설정 파일 변경 |

### 좋은 커밋 습관

**언제 커밋할까?** 하나의 작업 단위가 완성됐을 때 커밋합니다.

| 상황 | 권장 여부 |
| :---- | :---: |
| 버튼 컴포넌트 UI 완성 | ✅ |
| API 연동 완성 | ✅ |
| 빌드 에러가 나는 상태 | ❌ |
| UI · 이벤트 · API를 한 커밋에 | ❌ |

**커밋 전 확인 습관**

git diff        \# 내가 바꾼 내용을 눈으로 확인

git status      \# 의도하지 않은 파일이 포함되지 않았는지 확인

---

## 4\. 이슈 활용법

이슈는 단순한 할 일 목록이 아닙니다. **왜 이 코드를 작성했는지** 나중에도 추적할 수 있게 해주는 기록입니다. 코드 변경은 반드시 이슈에서 출발합니다.

### 이슈는 언제 만드나

- 새로운 기능을 개발할 때  
- 버그를 발견했을 때  
- 개발 작업을 등록할 때

### 어떤 템플릿을 쓸까

| 상황 | 템플릿 |
| :---- | :---- |
| "이 기능이 있었으면 좋겠다" | **기능 요청** |
| "이게 이상하게 동작한다" | **버그 리포트** |
| "이 작업을 해야 한다" | **작업** |

이슈를 생성할 때 **담당자(Assignee)** 와 **마일스톤**을 함께 지정합니다. 이슈가 생성되면 칸반 보드 **Backlog**에 자동으로 추가됩니다.

### 이슈 템플릿

기능 요청은 별도 템플릿 없이 스크럼에서 논의 후 확정된 것만 작업 이슈로 등록합니다. PR 리뷰 중 아이디어가 나왔다면 댓글 우측 `...` → **Create issue from comment**로 바로 이슈를 만드세요.

#### 버그 리포트 (`.github/ISSUE_TEMPLATE/bug_report.md`)

\---

name: 버그 리포트

about: 버그를 제보합니다

title: "\[BUG\] "

labels: bug

assignees: ""

\---

\#\# 버그 요약

\<\!-- 어떤 버그인지 한 문장으로 설명해 주세요. \--\>

\#\# 재현 방법

1\. 

2\. 

3\. 

\#\# 기대 동작

\<\!-- 정상적으로 동작했다면 어떤 결과가 나와야 하나요? \--\>

\#\# 실제 동작

\<\!-- 실제로는 어떤 결과가 나왔나요? \--\>

\#\# 환경 정보

\- OS: 

\- 브라우저 / 런타임 버전: 

\- 관련 패키지 버전: 

\#\# 스크린샷 / 로그

\<\!-- 오류 화면이나 로그가 있다면 첨부해 주세요. (선택) \--\>

#### 작업 (`.github/ISSUE_TEMPLATE/task.md`)

\---

name: 개발 작업

about: 개발 작업을 등록합니다

title: "\[TASK\] "

labels: task

assignees: ""

\---

\#\# 작업 내용

\<\!-- 어떤 작업을 해야 하는지 설명해 주세요. \--\>

\#\# 완료 조건 (Acceptance Criteria)

\- \[ \] 

\- \[ \] 

\- \[ \] 

\#\# 관련 이슈

\<\!-- 연관된 이슈 번호가 있다면 작성해 주세요. (선택) \--\>

\- \#

---

## 5\. PR 가이드

### PR 열기

1. GitHub에서 작업한 브랜치로 이동  
2. **Compare & pull request** 버튼 클릭  
3. base 브랜치가 `develop`인지 확인  
4. PR 설명란에 템플릿이 자동으로 채워집니다 — 빈칸을 채워주세요

### PR 템플릿 (`.github/PULL_REQUEST_TEMPLATE.md`)

\#\# 개요

\<\!-- 이 PR에서 무엇을 변경했는지 간략하게 설명해 주세요. \--\>

\#\# 변경 사항

\<\!-- 주요 변경 내용을 목록으로 작성해 주세요. \--\>

\- 

\- 

\#\# 관련 이슈

\<\!-- 연결된 이슈 번호를 작성하면 PR Merge 시 자동으로 이슈가 닫힙니다. \--\>

Closes \#

\#\# 테스트 방법

\<\!-- 리뷰어가 직접 테스트할 수 있도록 방법을 안내해 주세요. \--\>

1\. 

2\. 

3\. 

\#\# 스크린샷

\<\!-- UI 변경이 있을 경우 before/after 스크린샷을 첨부해 주세요. (선택) \--\>

| Before | After |

|---|---|

|  |  |

\#\# 체크리스트

\- \[ \] 커밋 컨벤션을 준수했습니다.

\- \[ \] 관련 이슈와 연결했습니다.

\- \[ \] 셀프 코드 리뷰를 완료했습니다.

\- \[ \] 문서(README 등)를 업데이트했습니다. (해당하는 경우)

### PR 작성 시 주의사항

- **`Closes #이슈번호`** 를 반드시 작성하세요. Merge 시 이슈가 자동으로 닫히고 칸반이 Done으로 이동합니다.  
- 스스로 Merge하지 않습니다. 승인 2개를 받은 뒤 Merge합니다.  
- PR 하나에는 하나의 이슈만 연결합니다.

---

## 6\. 코드 리뷰 가이드

코드 리뷰는 팀의 코드 품질을 함께 책임지는 과정입니다. 형식적인 Approve는 의미가 없습니다.

### 리뷰어 체크리스트

PR을 승인하기 전에 아래를 직접 확인합니다.

- [ ] PR 설명의 테스트 방법대로 직접 실행해 봤는가  
- [ ] 코드가 이슈의 목적에 맞게 구현됐는가  
- [ ] 나중에 다른 팀원이 읽어도 이해할 수 있는 코드인가  
- [ ] 커밋 메시지가 컨벤션을 따르는가  
- [ ] 작업 범위 밖의 파일이 포함되지 않았는가

### GitHub 리뷰 기능 사용법

| 상황 | 사용할 기능 |
| :---- | :---- |
| 전체적으로 문제없음 | **Approve** |
| 꼭 수정이 필요한 부분이 있음 | **Request changes** \+ 코멘트 |
| 궁금한 점이나 제안이 있음 | **Comment** |

### 리뷰 에티켓

**리뷰어로서**

- "이 코드는 \~" 로 이야기합니다. 코드에 대해 이야기하지, 사람을 비판하지 않습니다.  
- "이건 잘못됐어요"가 아닌, **이유와 대안**을 함께 제시합니다.  
- 사소한 제안에는 앞에 `nit:` 를 붙여 필수 수정이 아님을 표시합니다.  
    
  nit: result 대신 response로 이름을 바꾸면 더 명확할 것 같아요.  
    
- PR이 올라오면 **하루 안에** 리뷰를 시작합니다.

**PR 작성자로서**

- Request changes를 받아도 방어적으로 반응하지 않습니다. 이유가 있다면 댓글로 설명합니다.  
- 수정이 완료되면 해당 댓글에서 **Resolve conversation**을 클릭합니다.  
- 리뷰 없이 스스로 Merge하지 않습니다.

---

## 7\. 칸반 보드 사용법

칸반 보드는 팀 전체의 작업 현황을 한눈에 볼 수 있는 공간입니다. 이슈 생성과 PR Merge는 자동으로 반영되고, 그 외 이동은 담당자가 직접 합니다.

### 컬럼 의미와 이동 시점

| 컬럼 | 의미 | 언제 이동하나 |
| :---- | :---- | :---- |
| **Backlog** | 등록된 이슈가 모이는 곳 | 이슈 생성 시 자동 추가 |
| **To Do** | 이번에 할 작업 | 팀 리더가 스프린트 계획 시 이동 |
| **In Progress** | 현재 개발 중 | 브랜치를 만들고 작업 시작할 때 직접 이동 |
| **In Review** | PR 리뷰 중 | PR을 열었을 때 직접 이동 |
| **Done** | 완료 | PR Merge 시 자동 이동 |

### 운영 규칙

- **In Progress는 1인 1카드**를 원칙으로 합니다. 하나를 끝내고 다음을 시작하세요.  
- 작업이 막혀 며칠째 In Progress에 있다면, 이슈 댓글로 상황을 공유하세요.  
- 매주 팀 회의에서 Backlog를 검토하고 다음 작업을 To Do로 이동합니다.

---

## 8\. 부록: 관리자 초기 설정

이 섹션은 팀 리더가 저장소를 처음 설정할 때 참고합니다. 팀원은 읽지 않아도 됩니다.

### 브랜치 보호 규칙 (Branch Protection Rules)

Repository → Settings → Branches → **Add branch protection rule** `main`과 `develop` 각각 아래 옵션을 적용합니다.

✅ Require a pull request before merging

    ✅ Require approvals: 2

    ✅ Dismiss stale pull request approvals when new commits are pushed

✅ Require conversation resolution before merging

✅ Do not allow bypassing the above settings

### 라벨 생성

Repository → Issues → **Labels** → **New label**

| 라벨 | 색상 |
| :---- | :---- |
| `enhancement` | `#a2eeef` |
| `bug` | `#d73a4a` |
| `task` | `#e4e669` |

### 마일스톤 생성

Repository → Issues → **Milestones** → **New milestone**

| 마일스톤 | 시점 |
| :---- | :---- |
| `v0.1 - 공통 컴포넌트` | 1단계 완료 시 |
| `v1.0 - 최종 배포` | 프로젝트 마감일 |

### 기타 저장소 설정

- Repository → Settings → General → **Automatically delete head branches** 활성화  
- Repository → Settings → General → Merge 방식: **Allow squash merging** 만 체크  
  - Default commit message: **Pull request title and description**

### 칸반 보드 Workflow 설정

Project → Settings → **Workflows**

- `Item added to project` → Status: **Backlog** 활성화  
- `Pull request merged` → Status: **Done** 활성화

### 버전 배포 (`develop` → `main`)

\# develop → main PR을 생성하고 Merge한 뒤 태그를 붙입니다

git switch main

git pull origin main

git tag \-a v1.0.0 \-m "v1.0.0: 로그인·회원가입·대시보드 완성"

git push origin v1.0.0

---

## .github 디렉터리 구조

.github/

├── ISSUE\_TEMPLATE/

│   ├── bug\_report.md

│   └── task.md

└── PULL\_REQUEST\_TEMPLATE.md

---

궁금한 점이나 이 가이드에서 이해가 안 되는 부분이 있으면 언제든 팀 채널에 질문하세요.  
