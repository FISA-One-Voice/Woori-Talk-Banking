# app/ 라우트 구조 (Expo Router)

| 폴더 | URL | 용도 |
|------|-----|------|
| `index.tsx` | `/` | 개발 진입 (테스트 / 앱 진입) |
| `dev/` | `/dev` | 테스트 허브 (쇼케이스·API 등 개발용만) |
| `home/` | `/home` | 본앱 홈 (기능은 여기서 분기) |
| `showcase/` | `/showcase` | 공통 컴포넌트 쇼케이스 |

## 기능 추가 시

담당 화면은 `app/` 아래 폴더로 추가합니다.

```
app/balance/index.tsx   → /balance
app/transfer/index.tsx  → /transfer
```

`constants/homeMenu.ts` 의 `route` 에 경로를 연결합니다.
