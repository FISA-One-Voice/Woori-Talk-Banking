// =============================================================================
// app/dev/home/index.tsx
//
// [이 파일의 역할]
// dev 환경에서 홈 화면을 테스트하는 라우트입니다.
// HomeScreen 컴포넌트에 dev 경로를 주입합니다.
//
// [실제 앱 조립 시]
// app/home/index.tsx 에서 실제 경로로 교체합니다.
// 이 파일은 수정하지 않아도 됩니다.
// =============================================================================

import HomeScreen from '@/components/screens/HomeScreen';
import { router } from 'expo-router';

export default function DevHomeRoute() {
  return (
    <HomeScreen
      onEventBannerPress={(id) => router.push(`/dev/event/${id}` as never)}
      onEventMenuPress={() => router.push('/dev/event' as never)}
      // TODO: 각 담당자 기능 완성 후 아래 주석 해제 및 경로 연결
      // onTransferPress={() => router.push('/dev/transfer')}
      // onAssetPress={() => router.push('/dev/asset')}
      // onAutoTransferPress={() => router.push('/dev/auto-transfer')}
    />
  );
}
