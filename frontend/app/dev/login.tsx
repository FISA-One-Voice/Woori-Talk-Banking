import { useState } from 'react';
import { SafeAreaView, StyleSheet, Text, TextInput, View, Pressable, Alert, Keyboard } from 'react-native';
import { router } from 'expo-router';
import { TopBar } from '@/components/layout';
import { AccessibleNumKeypad } from '@/components/input';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';

export default function DevLoginScreen() {
  const [phone, setPhone] = useState('');
  const [step, setStep] = useState<'PHONE' | 'PIN'>('PHONE');
  
  const handlePhoneComplete = (completedPhone: string) => {
    // 11자리가 다 입력되면 자동으로 형식을 맞추고 PIN 단계로 이동
    let formatted = completedPhone;
    if (completedPhone.length === 11) {
      formatted = `${completedPhone.slice(0, 3)}-${completedPhone.slice(3, 7)}-${completedPhone.slice(7, 11)}`;
    }
    setPhone(formatted);
    setStep('PIN');
  };

  const handleLogin = async (pinValue: string) => {
    try {
      // Mac의 로컬 IP를 사용하여 백엔드와 통신 (안드로이드/iOS 실기기 테스트용)
      const response = await fetch('http://172.21.27.62:8000/users/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ phone, pin: pinValue }),
      });

      const result = await response.json();

      if (response.ok && result.success) {
        // 로그인 성공 시 발급받은 토큰을 들고 음성 등록 테스트 화면으로 이동합니다.
        router.push({
          pathname: '/dev/voice-register',
          params: { token: result.data.accessToken }
        });
      } else {
        Alert.alert('로그인 실패 🚫', result.message || '인증에 실패했습니다.');
      }
    } catch (error) {
      Alert.alert('서버 연결 에러 🔌', '백엔드 서버가 켜져 있는지 확인해주세요!\n(http://172.21.27.62:8000)');
    }
  };

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.pad}>
        <TopBar variant="back" title="로그인 화면 테스트" onBack={() => router.back()} />
        
        <View style={styles.form}>
          {step === 'PHONE' ? (
            <View style={styles.stepContainer}>
              <View style={{ marginBottom: 12 }}>
                <Text style={styles.label}>전화번호 11자리</Text>
                <Text style={styles.subLabel}>번호를 모두 입력하면 PIN 입력으로 넘어갑니다.</Text>
              </View>
              <AccessibleNumKeypad 
                length={11} 
                mode="phone"
                onComplete={handlePhoneComplete} 
              />
            </View>
          ) : (
            <View style={styles.stepContainer}>
              <View style={styles.phoneSummary}>
                <Text style={styles.phoneSummaryText} accessibilityLabel={`입력된 전화번호: ${phone}`}>{phone}</Text>
                <Pressable onPress={() => setStep('PHONE')} accessibilityLabel="전화번호 수정하기">
                  <Text style={styles.editButtonText}>수정</Text>
                </Pressable>
              </View>

              <View style={{ marginTop: 24, marginBottom: 12 }}>
                <Text style={styles.label}>PIN 번호 (6자리)</Text>
                <Text style={styles.subLabel}>번호를 모두 입력하면 자동으로 로그인됩니다.</Text>
              </View>
              
              <AccessibleNumKeypad 
                length={6} 
                onComplete={handleLogin} 
              />
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
  form: {
    flex: 1,
    marginTop: 24,
    gap: 16,
  },
  label: {
    fontSize: FONT_SIZES.body,
    color: COLORS.highlightYellow,
    fontWeight: '600',
    marginBottom: 4,
  },
  subLabel: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.highlightYellow,
    marginTop: 4,
    marginBottom: 8,
  },
  stepContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: COLORS.surfaceLight,
    padding: 16,
    borderRadius: LAYOUT.borderRadius,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  phoneSummaryText: {
    fontSize: 24,
    color: COLORS.textMain,
    fontWeight: '600',
  },
  editButtonText: {
    fontSize: 20,
    color: COLORS.highlightYellow,
    fontWeight: '600',
  },
});
