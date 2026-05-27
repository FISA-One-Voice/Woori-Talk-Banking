import { useState, useEffect } from 'react';
import { SafeAreaView, StyleSheet, Text, View, Pressable, ActivityIndicator, Alert } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { TopBar } from '@/components/layout';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import { Ionicons } from '@expo/vector-icons';

type Step = 'TUTORIAL' | 'READY' | 'RECORDING' | 'SUCCESS' | 'FAIL';

export default function DevVoiceRegisterScreen() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const [step, setStep] = useState<Step>('TUTORIAL');
  const [recordCount, setRecordCount] = useState(1);
  const [loading, setLoading] = useState(false);

  // Ready -> Recording 자동 전환 (실제론 삐- 소리 후 전환됨)
  useEffect(() => {
    if (step === 'READY') {
      const timer = setTimeout(() => {
        setStep('RECORDING');
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [step]);

  // Recording 중 3초 뒤에 다음 횟수나 성공 화면으로 전환 (Mock)
  useEffect(() => {
    if (step === 'RECORDING') {
      const timer = setTimeout(() => {
        if (recordCount < 3) {
          setRecordCount((prev) => prev + 1);
          setStep('READY');
        } else {
          // 3회 완료 시 서버 전송
          handleRegisterVoice();
        }
      }, 2500);
      return () => clearTimeout(timer);
    }
  }, [step, recordCount]);

  const handleRegisterVoice = async () => {
    if (!token) {
      Alert.alert('오류', '로그인 토큰을 찾을 수 없습니다.');
      router.back();
      return;
    }
    setLoading(true);
    try {
      const dummyVector = Array(192).fill(0.1);
      const response = await fetch('http://172.21.27.62:8000/voice/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ embedding_vector: dummyVector }),
      });
      const result = await response.json();
      if (response.ok && result.success) {
        setStep('SUCCESS');
      } else {
        setStep('FAIL');
      }
    } catch (error) {
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
              {renderInfoBox('음성 안내', '처음 오셨군요!\n목소리 등록을 시작합니다')}
              
              <View style={styles.listContainer}>
                {[
                  '조용한 환경에서 진행해\n주세요',
                  '삐- 소리 후 말씀해 주세\n요',
                  '총 3회 반복합니다'
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
              {renderInfoBox('음성 안내', '삐- 소리 후\n말씀해 주세요')}
              <View style={styles.centerAction}>
                <View style={styles.micCircle}>
                  <Ionicons name="mic-outline" size={48} color={COLORS.highlightYellow} />
                </View>
                <Text style={styles.actionText}>대기 중</Text>
              </View>
            </View>
          )}

          {step === 'RECORDING' && (
            <View style={styles.stepContainer}>
              {renderInfoBox('음성 안내', `지금 말씀해 주세요\n(${recordCount}/3회)`)}
              <View style={styles.centerAction}>
                <View style={styles.recordingBadge}>
                  <View style={styles.recordingDot} />
                  <Text style={styles.recordingBadgeText}>녹음 중</Text>
                </View>
                {/* 오디오 파형(Mock) */}
                <View style={styles.waveContainer}>
                  {[1, 2, 3, 4, 5, 4, 3, 2, 1].map((h, i) => (
                    <View key={i} style={[styles.waveBar, { height: h * 10 }]} />
                  ))}
                </View>
                <Text style={styles.actionSubText}>{recordCount - 1}회 완료 - {4 - recordCount}회 남음</Text>
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
              
              {renderInfoBox('음성 안내', '목소리 등록 완료!\n로그인으로 이동합니다')}
              
              <View style={{ flex: 1, justifyContent: 'flex-end' }}>
                <Pressable style={styles.button} onPress={() => router.push('/dev')}>
                  <Text style={styles.buttonText}>로그인 화면으로 이동</Text>
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
                <Text style={[styles.infoLabel, { color: '#F87171' }]}>오류</Text>
                <Text style={styles.infoDesc}>소음이 감지되었습니다.\n다시 시도해 주세요</Text>
              </View>
              
              <View style={{ flex: 1, justifyContent: 'flex-end' }}>
                <Pressable style={[styles.button, { backgroundColor: 'transparent', borderWidth: 1, borderColor: COLORS.grayMedium }]} onPress={() => { setRecordCount(1); setStep('TUTORIAL'); }}>
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
  waveContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    height: 60,
    gap: 4,
    marginBottom: 32,
  },
  waveBar: {
    width: 6,
    backgroundColor: COLORS.highlightYellow,
    borderRadius: 3,
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
