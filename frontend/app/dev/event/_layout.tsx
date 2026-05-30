// =============================================================================
// app/dev/event/_layout.tsx
//
// 이벤트 화면 테스트 영역 레이아웃.
// MicProvider 로 감싸서 useMic() 사용 가능하게 합니다.
// =============================================================================

import { MicProvider } from '@/context/MicContext';
import { Stack } from 'expo-router';

export default function DevEventLayout() {
  return (
    <MicProvider>
      <Stack screenOptions={{ headerShown: false }} />
    </MicProvider>
  );
}
