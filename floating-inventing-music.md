# Plan: 앱 시작 시 로그인 화면으로 바로 이동

## Context
앱 최초 진입점(`app/index.tsx`)이 개발용 메뉴(테스트 허브, 쇼케이스, 로그인)를 보여주고 있어 실제 앱처럼 로그인 화면이 바로 나오지 않음. 프로덕션 빌드에서도 `/home`으로 리다이렉트되는 문제가 있음.

## 변경 파일

**`frontend/app/index.tsx`** — 1개 파일만 수정

### 현재 코드
```tsx
export default function Index() {
  if (!__DEV__) {
    return <Redirect href="/home" />;  // 프로덕션: 홈으로
  }
  // 개발: 테스트 허브 메뉴 렌더링
  return ( ... );
}
```

### 변경 후 코드
```tsx
import { Redirect } from 'expo-router';

export default function Index() {
  return <Redirect href="/login" />;
}
```

- `__DEV__` 분기 제거, 항상 `/login`으로 리다이렉트
- 기존 스타일, 메뉴 버튼 코드 전부 삭제 (미사용)
- `/dev`, `/showcase`는 경로 직접 입력으로 접근 가능하므로 유지

## 검증
앱 재시작 시 테스트 허브 메뉴 없이 로그인 화면이 바로 표시되는지 확인
