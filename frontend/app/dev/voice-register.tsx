import { useState, useEffect, useRef } from 'react';
import { SafeAreaView, StyleSheet, Text, View, Pressable, ActivityIndicator, Alert, Vibration } from 'react-native';
import { router } from 'expo-router';
import { TopBar } from '@/components/layout';
import VoiceWaveAnimation from '@/components/feedback/VoiceWaveAnimation';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import { Ionicons } from '@expo/vector-icons';
import { apiClient, ApiResponse } from '@/utils/api';
import { useAuthStore } from '@/store/authStore';
import { Audio } from 'expo-av';
import * as Speech from 'expo-speech';

type Step = 'TUTORIAL' | 'READY' | 'RECORDING' | 'SUCCESS' | 'FAIL';

export default function DevVoiceRegisterScreen() {
  const [step, setStep] = useState<Step>('TUTORIAL');
  const [loading, setLoading] = useState(false);
  const [audioLevel, setAudioLevel] = useState(-160);
  const [timeLeft, setTimeLeft] = useState(10);
  
  const recordingRef = useRef<Audio.Recording | null>(null);

  // 화면 단계에 따른 TTS(음성 읽어주기) 및 자동 전환 제어
  useEffect(() => {
    Speech.stop();

    if (step === 'TUTORIAL') {
      Speech.speak("고객님의 목소리 등록을 시작합니다. 준비사항. 1. 조용한 환경에서 진행해 주세요. 2. 진동이 울리면 문장을 천천히 세 번 연속으로 읽어주세요. 3. 총 10초동안 녹음됩니다. 준비가 되셨다면 화면 하단의 시작하기 버튼을 눌러주세요.", { language: 'ko-KR', rate: 0.9 });
    } else if (step === 'READY') {
      const message = "진동이 울리면, 내 목소리가 나의 비밀번호입니다 라는 문장을 천천히 세 번 연속으로 말씀해 주세요.";
      
      Speech.speak(message, {
        language: 'ko-KR',
        rate: 0.9,
        onDone: () => {
          setTimeout(() => {
            Vibration.vibrate(400); // 400ms 동안 확실하게 진동 트리거
            
            // 진동이 완전히 끝날 때까지 0.5초 기다린 후에 마이크를 켭니다.
            // (마이크가 켜지는 순간 OS가 진동을 강제로 끊어버리기 때문)
            setTimeout(() => {
              setStep('RECORDING');
            }, 500);
          }, 1500);
        },
        onError: () => {
          setTimeout(() => {
            Vibration.vibrate(400);
            setTimeout(() => {
              setStep('RECORDING');
            }, 500);
          }, 1500);
        }
      });
    } else if (step === 'SUCCESS') {
      Speech.speak("성공적으로 등록되었습니다. 이제 목소리로 간편하게 인증할 수 있습니다.", { language: 'ko-KR', rate: 0.9 });
    } else if (step === 'FAIL') {
      Speech.speak("목소리 인식에 실패했습니다. 조용한 곳에서 다시 시도해 주세요.", { language: 'ko-KR', rate: 0.9 });
    }

    return () => {
      Speech.stop();
    };
  }, [step]);

  // 녹음 단계 진입 시 마이크 켜기 & 15초 카운트다운
  useEffect(() => {
    let timerInterval: NodeJS.Timeout;
    let timeout: NodeJS.Timeout;

    if (step === 'RECORDING') {
      setTimeLeft(10);
      startRecording();

      // 1초마다 남은 시간 업데이트
      timerInterval = setInterval(() => {
        setTimeLeft((prev) => {
          if (prev <= 1) {
            clearInterval(timerInterval);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);

      // 15초 뒤 무조건 마이크 끄고 전송
      timeout = setTimeout(async () => {
        clearInterval(timerInterval);
        const uri = await stopRecording();
        
        if (uri) {
          await handleRegisterVoice(uri);
        } else {
          setStep('FAIL');
        }
      }, 10000);
    }

    return () => {
      if (timerInterval) clearInterval(timerInterval);
      if (timeout) clearTimeout(timeout);
    };
  }, [step]);

  const startRecording = async () => {
    try {
      // 기존에 덜 닫힌 녹음 세션이 있다면 확실하게 해제(Clean-up)합니다.
      if (recordingRef.current) {
        try {
          await recordingRef.current.stopAndUnloadAsync();
        } catch (e) {}
        recordingRef.current = null;
      }

      await Audio.requestPermissionsAsync();
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      const WAV_RECORDING_OPTIONS: Audio.RecordingOptions = {
        isMeteringEnabled: true,
        android: {
          extension: '.m4a',
          outputFormat: Audio.AndroidOutputFormat.MPEG_4,
          audioEncoder: Audio.AndroidAudioEncoder.AAC,
          sampleRate: 16000,
          numberOfChannels: 1,
          bitRate: 128000,
        },
        ios: {
          extension: '.wav',
          audioQuality: Audio.IOSAudioQuality.HIGH,
          sampleRate: 16000,
          numberOfChannels: 1,
          bitRate: 128000,
          linearPCMBitDepth: 16,
          linearPCMIsBigEndian: false,
          linearPCMIsFloat: false,
        },
        web: {
          mimeType: 'audio/webm',
          bitsPerSecond: 128000,
        },
      };

      const { recording } = await Audio.Recording.createAsync(WAV_RECORDING_OPTIONS);

      // 마이크 입력 레벨(볼륨)을 100ms 간격으로 가져와서 애니메이션에 전달
      recording.setOnRecordingStatusUpdate((status) => {
        if (status.isRecording && status.metering !== undefined) {
          setAudioLevel(status.metering);
        }
      });
      recording.setProgressUpdateInterval(100);

      recordingRef.current = recording;
    } catch (err) {
      console.error('Failed to start recording', err);
      Alert.alert('오류', '마이크 접근 권한이 필요합니다.');
    }
  };

  const stopRecording = async () => {
    if (!recordingRef.current) return null;
    try {
      await recordingRef.current.stopAndUnloadAsync();
      const uri = recordingRef.current.getURI();
      recordingRef.current = null;
      return uri;
    } catch (err) {
      console.error('Failed to stop recording', err);
      return null;
    }
  };

  const handleRegisterVoice = async (uri: string) => {
    // apiClient 인터셉터가 토큰을 자동 첨부하지만, 클라이언트 단에서 1차 방어
    const token = useAuthStore.getState().token;
    if (!token) {
      Alert.alert('오류', '로그인 토큰을 찾을 수 없습니다.');
      router.back();
      return;
    }
    
    setLoading(true);
    try {
      const formData = new FormData();
      // iOS에서는 .wav로 녹음되므로, 확장자를 동적으로 처리하거나 .wav로 기본 전송합니다.
      const isWav = uri.endsWith('.wav');
      formData.append('file', {
        uri: uri,
        name: isWav ? 'voice.wav' : 'voice.m4a',
        type: isWav ? 'audio/wav' : 'audio/m4a'
      } as any);

      const response = await apiClient.post<ApiResponse>('/api/voice/register', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 60000, // 백엔드 로직이 완전히 끝날 때까지 기다리도록 60초로 대폭 연장
      });
      
      const result = response.data;
      if (result.success) {
        setStep('SUCCESS');
      } else {
        setStep('FAIL');
      }
    } catch (error) {
      console.error('Voice registration error:', error);
      setStep('FAIL');
    } finally {
      setLoading(false);
    }
  };

  const renderInfoBox = (title: string, desc: string) => (
    <View style={styles.infoBox}>
      <Text style={styles.infoLabel}>{title}</Text>
      <Text style={styles.infoDesc}>{desc}</Text>
    </View>
  );

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.pad}>
        <TopBar variant="back" title="" onBack={() => router.back()} />
        
        <View style={styles.content}>
          
          {step === 'TUTORIAL' && (
            <View style={styles.stepContainer}>
              {renderInfoBox('음성 등록', '내 목소리가 나의 \n비밀번호입니다.\n안전한 뱅킹을 위해 등록해 주세요')}
              
              <View style={styles.listContainer}>
                {[
                  '조용한 환경에서 진행해 주세요',
                  '진동이 울리면 세 번 연속으로 읽어주세요',
                  '총 10초 동안 녹음됩니다'
                ].map((text, idx) => (
                  <View key={idx} style={styles.listItem}>
                    <View style={styles.listNumber}>
                      <Text style={styles.listNumberText}>{idx + 1}</Text>
                    </View>
                    <Text style={styles.listText}>{text}</Text>
                  </View>
                ))}
              </View>

              <View style={{ flex: 1, justifyContent: 'flex-end' }}>
                <Pressable style={styles.button} onPress={() => setStep('READY')}>
                  <Text style={styles.buttonText}>시작하기</Text>
                </Pressable>
              </View>
            </View>
          )}

          {step === 'READY' && (
            <View style={styles.stepContainer}>
              {renderInfoBox('준비해 주세요', '잠시 후 녹음이 시작됩니다.\n아래 문장을 읽을 준비를 해 주세요.')}
              <View style={styles.centerAction}>
                <View style={[styles.micCircle, { borderColor: COLORS.grayMedium }]}>
                  <Ionicons name="mic-outline" size={48} color={COLORS.grayMedium} />
                </View>
                <Text style={[styles.actionText, { fontSize: 24, fontWeight: 'bold', color: COLORS.highlightYellow, marginTop: 20 }]}>
                  "내 목소리가 나의 비밀번호입니다"
                </Text>
              </View>
            </View>
          )}

          {step === 'RECORDING' && (
            <View style={styles.stepContainer}>
              {renderInfoBox(`녹음 진행 중 (남은 시간: ${timeLeft}초)`, `화면의 문장을 천천히 3번\n읽어주세요!`)}
              <View style={styles.centerAction}>
                <View style={styles.recordingBadge}>
                  <View style={styles.recordingDot} />
                  <Text style={styles.recordingBadgeText}>녹음 중</Text>
                </View>
                
                <Text style={[styles.actionText, { fontSize: 28, fontWeight: 'bold', color: COLORS.highlightYellow, marginBottom: 40 }]}>
                  "내 목소리가 나의 비밀번호입니다"
                </Text>

                {/* 실제 음성 크기(audioLevel)에 실시간으로 반응하는 애니메이션 */}
                <VoiceWaveAnimation isActive={step === 'RECORDING'} audioLevel={audioLevel} />
              </View>
            </View>
          )}

          {step === 'SUCCESS' && (
            <View style={styles.stepContainer}>
              <View style={styles.centerActionSuccess}>
                <View style={styles.checkCircleLine}>
                  <Ionicons name="checkmark" size={60} color="#4ADE80" />
                </View>
                <Text style={styles.successTitleText}>등록 완료</Text>
              </View>
              
              {renderInfoBox('등록 완료', '성공적으로 등록되었습니다!\n이제 목소리로 간편하게 인증하세요.')}
              
              <View style={{ flex: 1, justifyContent: 'flex-end' }}>
                <Pressable style={styles.button} onPress={() => router.push('/dev')}>
                  <Text style={styles.buttonText}>홈 화면으로 이동</Text>
                </Pressable>
              </View>
            </View>
          )}

          {step === 'FAIL' && (
            <View style={styles.stepContainer}>
              <View style={styles.centerActionSuccess}>
                <View style={styles.failCircleLine}>
                  <Ionicons name="close" size={60} color="#F87171" />
                </View>
                <Text style={styles.failTitleText}>등록 실패</Text>
              </View>
              
              <View style={[styles.infoBox, { backgroundColor: '#3f1a1a', borderColor: '#5c2222' }]}>
                <Text style={[styles.infoLabel, { color: '#F87171' }]}>인증 오류</Text>
                <Text style={styles.infoDesc}>{"소음이 크거나 목소리가 \n작습니다. 조용한 곳에서 다시 \n시도해 주세요."}</Text>
              </View>
              
              <View style={{ flex: 1, justifyContent: 'flex-end' }}>
                <Pressable style={[styles.button, { backgroundColor: 'transparent', borderWidth: 1, borderColor: COLORS.grayMedium }]} onPress={() => { setStep('TUTORIAL'); }}>
                  <Text style={[styles.buttonText, { color: COLORS.textMain }]}>처음부터 다시 시도하기</Text>
                </Pressable>
              </View>
            </View>
          )}
          
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  pad: {
    flex: 1,
    padding: LAYOUT.paddingMedium,
  },
  content: {
    flex: 1,
  },
  stepContainer: {
    flex: 1,
  },
  infoBox: {
    backgroundColor: '#1C1C16',
    borderWidth: 1,
    borderColor: '#363628',
    borderRadius: 16,
    padding: 24,
    marginBottom: 40,
  },
  infoLabel: {
    color: '#A1A18A',
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 8,
  },
  infoDesc: {
    color: COLORS.textMain,
    fontSize: 24,
    fontWeight: '700',
    lineHeight: 34,
  },
  listContainer: {
    gap: 20,
  },
  listItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1E1E1E',
    padding: 16,
    borderRadius: 12,
  },
  listNumber: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: COLORS.highlightYellow,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 16,
  },
  listNumberText: {
    color: '#000',
    fontWeight: 'bold',
    fontSize: 14,
  },
  listText: {
    color: COLORS.textMain,
    fontSize: 16,
    lineHeight: 22,
  },
  centerAction: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 100,
  },
  micCircle: {
    width: 120,
    height: 120,
    borderRadius: 60,
    borderWidth: 2,
    borderColor: COLORS.highlightYellow,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
  },
  actionText: {
    color: COLORS.textMain,
    fontSize: 18,
    fontWeight: '500',
  },
  recordingBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1A331E',
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 20,
    marginBottom: 40,
  },
  recordingDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#4ADE80',
    marginRight: 8,
  },
  recordingBadgeText: {
    color: '#4ADE80',
    fontWeight: '600',
  },
  actionSubText: {
    color: COLORS.grayMedium,
    fontSize: 14,
  },
  centerActionSuccess: {
    alignItems: 'center',
    marginTop: 40,
    marginBottom: 40,
  },
  checkCircleLine: {
    width: 100,
    height: 100,
    borderRadius: 50,
    borderWidth: 3,
    borderColor: '#4ADE80',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  failCircleLine: {
    width: 100,
    height: 100,
    borderRadius: 50,
    borderWidth: 3,
    borderColor: '#F87171',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  successTitleText: {
    color: COLORS.textMain,
    fontSize: 24,
    fontWeight: 'bold',
  },
  failTitleText: {
    color: '#F87171',
    fontSize: 24,
    fontWeight: 'bold',
  },
  button: {
    backgroundColor: COLORS.highlightYellow,
    width: '100%',
    paddingVertical: 20,
    borderRadius: LAYOUT.borderRadius,
    alignItems: 'center',
    marginBottom: 16,
  },
  buttonText: {
    fontSize: FONT_SIZES.button,
    color: COLORS.background,
    fontWeight: '700',
  },
});
