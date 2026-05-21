# Woori-Talk-Banking

시각장애인을 위한 음성 기반 뱅킹 앱 — 부트캠프 팀 프로젝트 (6인)

---

## 개발 환경 세팅

개발 시작 전 [SETUP.md](SETUP.md) 를 참고해서 환경을 세팅해주세요.

---

## 디렉토리 구조

```
Woori-Talk-Banking/
│
├── frontend/                    # React Native (TypeScript) + Expo
│   ├── app/                     # Expo Router — 파일 위치 = 화면 URL
│   ├── components/              # 공통 UI 컴포넌트
│   ├── constants/               # 공통 상수 (테마 등)
│   ├── hooks/                   # 커스텀 훅 (useVoiceInput, useTTS 등)
│   ├── services/                # 백엔드 API 호출 함수
│   ├── store/                   # Zustand 전역 상태
│   ├── types/                   # TypeScript 타입 정의
│   ├── assets/                  # 이미지, 폰트 등 정적 리소스
│   ├── app.json
│   └── package.json
│
├── backend/                     # FastAPI (Python 3.11)
│   ├── app/
│   │   ├── main.py              # 서버 진입점 — 라우터 등록
│   │   ├── core/                # DB 연결, JWT, 환경변수
│   │   ├── features/            # 기능별 모듈 (router / service / schema)
│   │   ├── shared/
│   │   │   └── agent/           # LangChain Agent (의도 파악 + Slot Filling)
│   │   └── models/              # SQLAlchemy ORM 모델
│   ├── requirements.txt
│   └── pyproject.toml
│
├── ai/                          # EC2에 별도 배포하는 ML 모델 서버
│   ├── asv/                     # 화자 인증 (WavLM) — FastAPI: POST /verify
│   └── anti-spoofing/           # 위조 음성 탐지 — FastAPI: POST /detect
│
└── .github/                     # PR 템플릿, 이슈 템플릿
```

