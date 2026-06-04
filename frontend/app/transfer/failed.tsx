import { useCallback, useEffect, useRef } from 'react';
import { SafeAreaView, StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { TopBar } from '@/components/layout';
import { TRANSFER_FAILED_HOME_SUFFIX } from '@/constants/voicePrompts';
import { COLORS, LAYOUT } from '@/constants/theme';
import { fetchTtsAudio } from '@/services/voiceService';
import { useTransferStore } from '@/store/transferStore';
import { useVoiceResponseStore } from '@/store/voiceResponseStore';
import { playBase64Audio } from '@/utils/audioPlayer';
import { getTtsMessage } from '@/utils/errorHandler';
import { resetVoiceSessionOnHome } from '@/utils/resetVoiceSession';
import { speakText, stopAllTts } from '@/utils/ttsManager';
import { TransferFailedView } from './views/TransferFailedView';

function withHomeNavSuffix(message: string): string {
  const suffix = TRANSFER_FAILED_HOME_SUFFIX.trim();
  if (message.includes(suffix)) return message;
  return `${message}${TRANSFER_FAILED_HOME_SUFFIX}`;
}

export default function TransferFailedScreen() {
  const transferFailure = useTransferStore((s) => s.transferFailure);
  const lastResponse = useVoiceResponseStore((s) => s.lastResponse);
  const touchAnnouncedRef = useRef(false);

  const goHome = useCallback(() => {
    useTransferStore.getState().setTransferFailure(null);
    resetVoiceSessionOnHome();
    router.replace('/home');
  }, []);

  useEffect(() => {
    if (!transferFailure?.message && !transferFailure?.code) {
      goHome();
    }
  }, [transferFailure, goHome]);

  const errorMessage = withHomeNavSuffix(
    transferFailure?.message ?? getTtsMessage(transferFailure?.code),
  );

  // 터치 송금 실패: TTS 안내 후 홈 이동 (음성 실패는 _layout에서 audio 재생 후 홈 처리)
  useEffect(() => {
    if (touchAnnouncedRef.current) return;
    if (!transferFailure?.message && !transferFailure?.code) return;
    if (lastResponse?.navigate_to === 'transfer/failed' && lastResponse?.audio) {
      return;
    }

    touchAnnouncedRef.current = true;
    let cancelled = false;

    (async () => {
      await stopAllTts();
      try {
        const base64 = await fetchTtsAudio(errorMessage);
        await playBase64Audio(base64);
      } catch {
        await speakText(errorMessage);
      }
      if (!cancelled) goHome();
    })();

    return () => {
      cancelled = true;
    };
  }, [
    transferFailure?.message,
    transferFailure?.code,
    errorMessage,
    lastResponse?.navigate_to,
    lastResponse?.audio,
    goHome,
  ]);

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.body}>
        <TopBar variant="back" title="송금" onBack={goHome} />
        <TransferFailedView errorMessage={errorMessage} onGoHome={goHome} />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.background },
  body: { flex: 1, paddingHorizontal: LAYOUT.paddingMedium },
});
