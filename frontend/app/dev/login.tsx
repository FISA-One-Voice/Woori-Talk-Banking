import { useState } from 'react';
import { SafeAreaView, StyleSheet, Text, View, Pressable, Alert } from 'react-native';
import { router } from 'expo-router';
import { TopBar } from '@/components/layout';
import { AccessibleNumKeypad } from '@/components/input';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import { useAuthStore } from '@/store/authStore';
import { apiClient, ApiResponse } from '@/utils/api';

export default function DevLoginScreen() {
  const [phone, setPhone] = useState('');
  const [step, setStep] = useState<'PHONE' | 'PIN'>('PHONE');
  
  const handlePhoneComplete = (completedPhone: string) => {
    let formatted = completedPhone;
    if (completedPhone.length === 11) {
      formatted = `${completedPhone.slice(0, 3)}-${completedPhone.slice(3, 7)}-${completedPhone.slice(7, 11)}`;
    }
    setPhone(formatted);
    setStep('PIN');
  };

  const handleLogin = async (pinValue: string) => {
    try {
      const response = await apiClient.post<ApiResponse<{ accessToken: string; refreshToken: string; hasVoiceRegistered: boolean }>>('/users/login', { 
        phone, 
        pin: pinValue 
      });

      const result = response.data;

      if (result.success && result.data) {
        // 새로 만든 setTokens를 통해 Access, Refresh 토큰 모두 저장
        useAuthStore.getState().setTokens(result.data.accessToken, result.data.refreshToken);
        
        if (result.data.hasVoiceRegistered) {
          router.replace('/home');
        } else {
          router.replace('/dev/voice-register');
        }
      } else {
        Alert.alert('로그인 실패 🚫', result.message || '인증에 실패했습니다.');
      }
    } catch (error: any) {
      const message = error.response?.data?.message || '인증에 실패했습니다.';
      if (error.response?.status && error.response.status !== 500) {
         Alert.alert('로그인 실패 🚫', message);
      } else {
         Alert.alert('서버 연결 에러 🔌', `백엔드 서버가 켜져 있는지 확인해주세요!\n(${process.env.EXPO_PUBLIC_API_BASE_URL})`);
      }
    }
  };

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.pad}>
        <TopBar variant="back" title="로그인 화면 테스트" onBack={() => router.back()} />
        
        <View style={styles.form}>
          {step === 'PHONE' ? (
            <View style={{ flex: 1 }}>
              <View>
                <Text style={styles.label}>전화번호 11자리</Text>
                <Text style={styles.subLabel}>번호를 모두 입력하면 PIN 입력으로 넘어갑니다.</Text>
              </View>
              
              <View style={{ flex: 1, justifyContent: 'space-between', paddingTop: 32 }}>
                <AccessibleNumKeypad 
                  length={11} 
                  onComplete={handlePhoneComplete} 
                  renderHeader={(currentValue) => {
                    let display = currentValue;
                    if (currentValue.length > 3 && currentValue.length <= 7) {
                      display = `${currentValue.slice(0, 3)}-${currentValue.slice(3)}`;
                    } else if (currentValue.length > 7) {
                      display = `${currentValue.slice(0, 3)}-${currentValue.slice(3, 7)}-${currentValue.slice(7)}`;
                    }
                    
                    return (
                      <View style={styles.phoneHeaderBox}>
                        <Text style={[styles.phoneHeaderText, currentValue.length === 0 && { color: COLORS.grayMedium }]}>
                          {currentValue.length === 0 ? '010-0000-0000' : display}
                        </Text>
                      </View>
                    );
                  }}
                />
              </View>
            </View>
          ) : (
            <View style={{ flex: 1 }}>
              <View style={styles.phoneSummary}>
                <Text style={styles.phoneSummaryText} accessibilityLabel={`입력된 전화번호: ${phone}`}>{phone}</Text>
                <Pressable onPress={() => setStep('PHONE')} accessibilityLabel="전화번호 수정하기">
                  <Text style={styles.editButtonText}>수정</Text>
                </Pressable>
              </View>

              <View style={{ marginTop: 24 }}>
                <Text style={styles.label}>PIN 번호 (6자리)</Text>
                <Text style={styles.subLabel}>번호를 모두 입력하면 자동으로 로그인됩니다.</Text>
              </View>
              
              <View style={{ flex: 1, justifyContent: 'space-between', paddingTop: 24 }}>
                <AccessibleNumKeypad 
                  length={6} 
                  onComplete={handleLogin} 
                />
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
  phoneHeaderBox: {
    alignItems: 'center',
    paddingVertical: 16,
    backgroundColor: COLORS.surfaceLight,
    borderRadius: LAYOUT.borderRadius,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  phoneHeaderText: {
    fontSize: 32,
    color: '#FFF080',
    fontWeight: '600',
    letterSpacing: 2,
  },
  phoneSummary: {
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
