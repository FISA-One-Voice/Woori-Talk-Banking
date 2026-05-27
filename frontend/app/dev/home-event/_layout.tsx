// =============================================================================
// app/dev/home-event/_layout.tsx
//
// 홈 화면 & 이벤트 구현 테스트 영역의 레이아웃.
// MicProvider 로 감싸서 이 영역 안의 모든 화면에서 useMic() 사용 가능.
// =============================================================================

import { MicProvider } from '@/context/MicContext';
import { Stack } from 'expo-router';

export default function HomeEventLayout() {
  return (
    <MicProvider>
      <Stack screenOptions={{ headerShown: false }} />
    </MicProvider>
  );
}
