import { useState } from 'react';
import { SafeAreaView, StyleSheet, Text, View, Pressable, ActivityIndicator, Alert } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { TopBar } from '@/components/layout';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';

export default function DevVoiceRegisterScreen() {
  const { token } = useLocalSearchParams<{ token: string }>();
  
  const [loading, setLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  // 음성 등록 MOCK 요청
  const handleRegisterVoice = async () => {
    if (!token) {
      Alert.alert('오류', '로그인 토큰을 찾을 수 없습니다. 다시 로그인해주세요.');
      router.back();
      return;
    }

    setLoading(true);

    try {
      // 192차원 더미 벡터 생성 (AI 모델 연동 전 임시 데이터)
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
        setIsSuccess(true);
      } else {
        Alert.alert('등록 실패 🚫', result.message || '음성 벡터 등록 중 오류가 발생했습니다.');
      }
    } catch (error) {
      Alert.alert('네트워크 오류 🔌', '서버와 연결할 수 없습니다. 백엔드가 켜져 있는지 확인하세요.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.pad}>
        <TopBar variant="back" title="음성 등록 테스트" onBack={() => router.back()} />
        
        <View style={styles.content}>
          {isSuccess ? (
            // 성공 화면
            <View style={styles.successContainer}>
              <View style={styles.checkCircle}>
                <Text style={styles.checkMark}>✓</Text>
              </View>
              <Text style={styles.successTitle}>음성 등록이 완료되었습니다</Text>
              <Text style={styles.successDesc}>
                이제 등록된 목소리로 본인 인증을 진행할 수 있습니다.
              </Text>
              
              <Pressable 
                style={[styles.button, { marginTop: 40 }]} 
                onPress={() => router.push('/dev')}
              >
                <Text style={styles.buttonText}>테스트 허브로 돌아가기</Text>
              </Pressable>
            </View>
          ) : (
            // 등록 대기 화면
            <View style={styles.registerContainer}>
              <Text style={styles.instruction}>
                "내 계좌 잔액 알려줘"
              </Text>
              <Text style={styles.subInstruction}>
                아래 버튼을 눌러 (가상) 음성 데이터를 서버로 전송합니다.
              </Text>

              <Pressable 
                style={[styles.button, loading && styles.buttonDisabled]} 
                onPress={handleRegisterVoice}
                disabled={loading}
              >
                {loading ? (
                  <ActivityIndicator color={COLORS.background} />
                ) : (
                  <Text style={styles.buttonText}>음성 등록 시작 (Mock 전송)</Text>
                )}
              </Pressable>
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
    justifyContent: 'center',
    alignItems: 'center',
  },
  
  // 성공 화면 스타일
  successContainer: {
    alignItems: 'center',
    width: '100%',
  },
  checkCircle: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: COLORS.highlightYellow,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
  },
  checkMark: {
    fontSize: 60,
    color: COLORS.background,
    fontWeight: 'bold',
  },
  successTitle: {
    fontSize: FONT_SIZES.button,
    color: COLORS.textMain,
    fontWeight: '700',
    marginBottom: 12,
  },
  successDesc: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
    textAlign: 'center',
    paddingHorizontal: 20,
  },

  // 등록 대기 화면 스타일
  registerContainer: {
    alignItems: 'center',
    width: '100%',
  },
  instruction: {
    fontSize: FONT_SIZES.title,
    color: COLORS.highlightYellow,
    fontWeight: '700',
    marginBottom: 16,
    textAlign: 'center',
  },
  subInstruction: {
    fontSize: FONT_SIZES.body,
    color: COLORS.textMain,
    textAlign: 'center',
    marginBottom: 48,
    paddingHorizontal: 20,
  },
  
  // 버튼 스타일
  button: {
    backgroundColor: COLORS.highlightYellow,
    width: '100%',
    paddingVertical: 20,
    borderRadius: LAYOUT.borderRadius,
    alignItems: 'center',
  },
  buttonDisabled: {
    opacity: 0.7,
  },
  buttonText: {
    fontSize: FONT_SIZES.button,
    color: COLORS.background,
    fontWeight: '700',
  },
});
