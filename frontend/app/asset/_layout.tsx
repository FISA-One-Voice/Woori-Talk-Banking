import { MicProvider } from '@/context/MicContext';
import { Stack } from 'expo-router';

export default function AssetLayout() {
  return (
    <MicProvider>
      <Stack screenOptions={{ headerShown: false }} />
    </MicProvider>
  );
}
