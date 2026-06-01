import { useState, useEffect, useRef } from 'react';
import { SafeAreaView, StyleSheet, Text, View, Pressable, ActivityIndicator, Alert } from 'react-native';
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

const SENTENCES = [
  "내 목소리가 나의 비밀번호입니다",
  "우리 톡 뱅킹으로 안전하게 이체해요",
  "오늘도 기분 좋은 하루 보내세요"
];

export default function DevVoiceRegisterScreen() {
  const [step, setStep] = useState<Step>('TUTORIAL');
  const [loading, setLoading] = useState(false);
  const [audioLevel, setAudioLevel] = useState(-160);
  const [recordingIndex, setRecordingIndex] = useState(0);
  const [recordingStatus, setRecordingStatus] = useState<'WAITING' | 'RECORDING' | 'UPLOADING'>('WAITING');
  
  const recordingRef = useRef<Audio.Recording | null>(null);

  const speakWithSpeaker = async (text: string, options: any = {}) => {
    try {
      const { sound: dummySound } = await Audio.Sound.createAsync(require('@/assets/sounds/beep.wav'));
      await dummySound.setVolumeAsync(0);
      await dummySound.playAsync();
      await dummySound.unloadAsync();
    } catch (e) {}
    await new Promise(resolve => setTimeout(resolve, 200));
    Speech.speak(text, options);
  };

  useEffect(() => {
    Audio.setAudioModeAsync({
      allowsRecordingIOS: false,
      playsInSilentModeIOS: true,
      playThroughEarpieceAndroid: false,
      staysActiveInBackground: false,
    });
    
    Speech.stop();

    if (step === 'TUTORIAL') {
      speakWithSpeaker("고객님의 목소리 등록을 시작합니다. 준비사항. 1. 조용한 환경에서 진행해 주세요. 2. 음성 안내가 끝나고 삐 소리가 나면 화면에 뜨는 문장을 천천히 읽어주세요. 3. 총 세 개의 문장을 녹음합니다. 준비가 되셨다면 화면 하단의 시작하기 버튼을 눌러주세요.", { language: 'ko-KR', rate: 0.9 });
    } else if (step === 'READY') {
      const message = "잠시 후 첫 번째 문장 녹음을 시작합니다.";
      speakWithSpeaker(message, {
        language: 'ko-KR',
        rate: 0.9,
        volume: 1.0,
        onDone: () => {
          setTimeout(() => {
            setStep('RECORDING');
          }, 500);
        }
      });
    } else if (step === 'SUCCESS') {
      speakWithSpeaker("고객님의 목소리가 성공적으로 등록되었습니다. 이제 목소리로 간편하게 인증할 수 있습니다. 감사합니다.", { language: 'ko-KR', rate: 0.9 });
    } else if (step === 'FAIL') {
      speakWithSpeaker("목소리 인식에 실패했습니다. 조용한 곳에서 다시 시도해 주세요.", { language: 'ko-KR', rate: 0.9 });
    }

    return () => {
      Speech.stop();
    };
  }, [step]);

  useEffect(() => {
    if (step === 'RECORDING') {
      startThreeSplitRecording();
    }
  }, [step]);

  const startThreeSplitRecording = async () => {
    const uris: string[] = [];
    try {
      await Audio.requestPermissionsAsync();
      
      for (let i = 0; i < 3; i++) {
        setRecordingIndex(i);
        setRecordingStatus('WAITING');
        
        // TTS 스피커 모드로 확실하게 전환하기 위해 잠시 대기
        await Audio.setAudioModeAsync({
          allowsRecordingIOS: false,
          playsInSilentModeIOS: true,
          playThroughEarpieceAndroid: false,
          staysActiveInBackground: false,
        });
        
        // [iOS 버그 해결 핵] expo-av는 실제로 소리를 재생해야 오디오 세션을 iOS 시스템에 적용(Commit)합니다.
        // 마이크 사용 후 수화기에 갇힌 소리를 스피커로 빼기 위해 TTS 직전에 묵음으로 오디오 세션을 강제 갱신합니다.
        try {
          const { sound: dummySound } = await Audio.Sound.createAsync(require('@/assets/sounds/beep.wav'));
          await dummySound.setVolumeAsync(0); // 소리 끄기
          await dummySound.playAsync();
          await dummySound.unloadAsync();
        } catch (e) {
          // ignore
        }
        
        await new Promise(resolve => setTimeout(resolve, 200));

        // TTS 안내: "삐 소리가 나면 ~라고 말해주세요."
        const sentence = SENTENCES[i];
        const prompt = `삐 소리가 나면, ${sentence} 라고 말해주세요.`;
        
        await new Promise<void>((resolve) => {
          Speech.speak(prompt, {
            language: 'ko-KR',
            rate: 0.9,
            volume: 1.0,
            onDone: () => resolve()
          });
        });

        // TTS 끝나면 실제 삐 소리 재생
        try {
          const { sound } = await Audio.Sound.createAsync(
            require('@/assets/sounds/beep.wav')
          );
          await sound.playAsync();
          // 삐 소리 재생 길이만큼 약간 대기 (0.4초)
          await new Promise(resolve => setTimeout(resolve, 400));
          await sound.unloadAsync();
        } catch (e) {
          console.error("삐 소리 재생 실패:", e);
        }

        // 삐 소리가 끝난 직후 마이크 켜기
        await Audio.setAudioModeAsync({
          allowsRecordingIOS: true,
          playsInSilentModeIOS: true,
          playThroughEarpieceAndroid: false,
          staysActiveInBackground: false,
        });

        setRecordingStatus('RECORDING');

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
        
        recording.setOnRecordingStatusUpdate((status) => {
          if (status.isRecording && status.metering !== undefined) {
            setAudioLevel(status.metering);
          }
        });
        recording.setProgressUpdateInterval(100);
        recordingRef.current = recording;
        
        // 3.3초 녹음 대기
        await new Promise(resolve => setTimeout(resolve, 3300));
        
        await recording.stopAndUnloadAsync();
        const uri = recording.getURI();
        if (uri) uris.push(uri);
        recordingRef.current = null;
        
        setRecordingStatus('WAITING');
        // 다음 문장 넘어가기 전 잠깐 대기 (iOS 오디오 세션 강제 초기화 포함)
        if (i < 2) {
          // iOS에서 마이크 사용 후 수화기로 소리가 갇히는 버그를 강제로 풀기 위해 오디오 시스템 껐다 켜기
          await Audio.setIsEnabledAsync(false);
          await new Promise(resolve => setTimeout(resolve, 100));
          await Audio.setIsEnabledAsync(true);
          
          await new Promise(resolve => setTimeout(resolve, 1000));
        }
      }
      
      setRecordingStatus('UPLOADING');
      await handleRegisterMultiVoice(uris);

    } catch (err) {
      console.error(err);
      setStep('FAIL');
    }
  };

  const handleRegisterMultiVoice = async (uris: string[]) => {
    setLoading(true);
    try {
      const formData = new FormData();
      uris.forEach((uri, index) => {
        const isWav = uri.endsWith('.wav');
        formData.append('files', {
          uri: uri,
          name: isWav ? `voice_${index}.wav` : `voice_${index}.m4a`,
          type: isWav ? 'audio/wav' : 'audio/m4a'
        } as any);
      });

      const response = await apiClient.post<ApiResponse>('/api/voice/register', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 60000,
      });
      
      if (response.data.success) {
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
                  '안내 후 삐 소리가 나면 화면의 문장을 읽어주세요',
                  '총 세 개의 문장을 녹음합니다'
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
              {renderInfoBox('준비해 주세요', '잠시 후 음성 안내가 \n시작됩니다.')}
              <View style={styles.centerAction}>
                <View style={[styles.micCircle, { borderColor: COLORS.grayMedium }]}>
                  <Ionicons name="volume-high" size={48} color={COLORS.grayMedium} />
                </View>
              </View>
            </View>
          )}

          {step === 'RECORDING' && (
            <View style={styles.stepContainer}>
              {renderInfoBox(
                `문장 녹음 중 [${recordingIndex + 1}/3]`, 
                recordingStatus === 'RECORDING' ? '지금 말씀해 주세요!' : '음성 안내를 듣고 대기하세요.'
              )}
              <View style={styles.centerAction}>
                {recordingStatus === 'RECORDING' ? (
                  <View style={[styles.recordingBadge, { backgroundColor: 'rgba(239, 68, 68, 0.2)' }]}>
                    <View style={[styles.recordingDot, { backgroundColor: '#EF4444' }]} />
                    <Text style={[styles.recordingBadgeText, { color: '#EF4444' }]}>마이크 켜짐</Text>
                  </View>
                ) : recordingStatus === 'WAITING' ? (
                  <View style={[styles.recordingBadge, { backgroundColor: 'rgba(107, 114, 128, 0.2)' }]}>
                    <Ionicons name="volume-high" size={14} color="#9CA3AF" style={{ marginRight: 6 }} />
                    <Text style={[styles.recordingBadgeText, { color: '#9CA3AF' }]}>음성 안내 듣는 중...</Text>
                  </View>
                ) : (
                  <View style={[styles.recordingBadge, { backgroundColor: 'rgba(250, 204, 21, 0.2)' }]}>
                    <ActivityIndicator size="small" color={COLORS.highlightYellow} style={{ marginRight: 6 }} />
                    <Text style={[styles.recordingBadgeText, { color: COLORS.highlightYellow }]}>서버 병합 업로드 중...</Text>
                  </View>
                )}
                
                <Text style={[
                  styles.actionText, 
                  { fontSize: 24, fontWeight: 'bold', marginBottom: 40, textAlign: 'center', lineHeight: 34 },
                  recordingStatus === 'RECORDING' ? { color: COLORS.highlightYellow } : { color: COLORS.grayMedium }
                ]}>
                  "{SENTENCES[recordingIndex]}"
                </Text>

                {recordingStatus === 'RECORDING' ? (
                  <VoiceWaveAnimation isActive={true} audioLevel={audioLevel} />
                ) : (
                  <View style={[styles.micCircle, { borderColor: COLORS.grayMedium, marginTop: 20 }]}>
                    <Ionicons name="mic-off" size={48} color={COLORS.grayMedium} />
                  </View>
                )}
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
              
              {renderInfoBox('등록 완료', '성공적으로 등록되었습니다!\n이제 목소리로 간편하게 \n인증하세요.')}
              
              <View style={{ flex: 1, justifyContent: 'flex-end' }}>
                <Pressable style={styles.button} onPress={() => router.replace('/dev/login')}>
                  <Text style={styles.buttonText}>다시 로그인 화면으로 이동</Text>
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
                <Text style={styles.infoDesc}>{"서버 업로드 중 오류가\n발생했습니다. 조용한 곳에서 다시 \n시도해 주세요."}</Text>
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
