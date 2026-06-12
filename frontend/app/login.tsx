import { AccessibleNumKeypad } from '@/components/input';
import { TopBar } from '@/components/layout';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import { useAuthStore } from '@/store/authStore';
import { apiClient, ApiResponse } from '@/utils/api';
import * as LocalAuthentication from 'expo-local-authentication';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Alert, Platform, Pressable, SafeAreaView, StyleSheet, Text, View } from 'react-native';

export default function DevLoginScreen() {
  const savedToken = useAuthStore((state) => state.token);
  const [phone, setPhone] = useState('');
  const [step, setStep] = useState<'PHONE' | 'PIN' | 'BIOMETRIC'>('PHONE');

  useEffect(() => {
    if (savedToken) {
      setStep('BIOMETRIC');
    }
  }, [savedToken]);

  useEffect(() => {
    if (step === 'BIOMETRIC') {
      const timer = setTimeout(() => {
        triggerBiometric();
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [step]);

  const triggerBiometric = async () => {
    try {
      const hasHardware = await LocalAuthentication.hasHardwareAsync();
      const isEnrolled = await LocalAuthentication.isEnrolledAsync();
      if (hasHardware && isEnrolled) {
        const result = await LocalAuthentication.authenticateAsync({
          promptMessage:
            Platform.OS === 'ios'
              ? 'Face ID로 앱을 잠금 해제합니다'
              : '지문/얼굴 등 생체 인증으로 잠금 해제합니다',
          cancelLabel: '취소',
          disableDeviceFallback: true,
        });
        if (result.success) {
          router.replace('/home');
        } else {
          // TS의 엄격한 타입 검사를 피하기 위해 any로 캐스팅하여 에러 코드를 확인합니다.
          const errorCode = (result as any).error;
          if (errorCode === 'missing_usage_description' || errorCode === 'not_available') {
            Alert.alert(
              Platform.OS === 'ios'
                ? 'Face ID 시뮬레이션 (Expo Go)'
                : '생체 인증 시뮬레이션 (Expo Go)',
              '현재 사용 중인 Expo Go 앱은 애플 정책상 Face ID 테스트를 제한하고 있습니다.\n테스트를 위해 Face ID 인증을 통과한 것으로 처리합니다!',
              [{ text: '확인', onPress: () => router.replace('/home') }],
            );
          } else {
            setStep('PHONE');
          }
        }
      } else {
        // 하드웨어가 없거나 에뮬레이터인 경우 바로 패스 (테스트용)
        Alert.alert(
          'Face ID 시뮬레이션',
          '생체 인증 기기가 아닙니다. 테스트를 위해 통과 처리합니다.',
          [{ text: '확인', onPress: () => router.replace('/home') }],
        );
      }
    } catch (e: any) {
      setStep('PHONE');
    }
  };

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
      const response = await apiClient.post<
        ApiResponse<{
          accessToken: string;
          refreshToken: string;
          hasVoiceRegistered: boolean;
          ttsSpeed?: number;
        }>
      >('/api/users/login', {
        phone,
        pin: pinValue,
      });

      const result = response.data;

      if (result.success && result.data) {
        useAuthStore
          .getState()
          .setTokens(
            result.data.accessToken,
            result.data.refreshToken,
            result.data.hasVoiceRegistered,
            result.data.ttsSpeed,
          );

        if (result.data.hasVoiceRegistered) {
          router.replace('/home');
        } else {
          router.replace('/voice-register');
        }
      } else {
        Alert.alert('로그인 실패 🚫', result.message || '인증에 실패했습니다.');
      }
    } catch (error: any) {
      const message = error.response?.data?.message || '인증에 실패했습니다.';
      if (error.response?.status && error.response.status !== 500) {
        Alert.alert('로그인 실패 🚫', message);
      } else {
        Alert.alert(
          '서버 연결 에러 🔌',
          `백엔드 서버가 켜져 있는지 확인해주세요!\n(${process.env.EXPO_PUBLIC_API_BASE_URL})`,
        );
      }
    }
  };

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.pad}>
        <TopBar variant="title" title="로그인" />

        <View style={styles.form}>
          {step === 'BIOMETRIC' ? (
            <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
              <Text
                style={{
                  color: COLORS.highlightYellow,
                  fontSize: 20,
                  fontWeight: '600',
                  marginBottom: 20,
                }}
              >
                {Platform.OS === 'ios' ? 'Face ID' : '생체'} 인증을 진행해주세요.
              </Text>
              <Pressable onPress={() => setStep('PHONE')} style={{ padding: 16 }}>
                <Text style={{ color: COLORS.grayMedium, fontSize: 16 }}>
                  화면에 얼굴을 가까이 가져다주세요.
                </Text>
              </Pressable>
            </View>
          ) : step === 'PHONE' ? (
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
                        <Text
                          style={[
                            styles.phoneHeaderText,
                            currentValue.length === 0 && { color: COLORS.grayMedium },
                          ]}
                        >
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
                <Text
                  style={styles.phoneSummaryText}
                  accessibilityLabel={`입력된 전화번호: ${phone}`}
                >
                  {phone}
                </Text>
                <Pressable onPress={() => setStep('PHONE')} accessibilityLabel="전화번호 수정하기">
                  <Text style={styles.editButtonText}>수정</Text>
                </Pressable>
              </View>

              <View style={{ marginTop: 24 }}>
                <Text style={styles.label}>PIN 번호 (6자리)</Text>
                <Text style={styles.subLabel}>번호를 모두 입력하면 자동으로 로그인됩니다.</Text>
              </View>

              <View style={{ flex: 1, justifyContent: 'space-between', paddingTop: 24 }}>
                <AccessibleNumKeypad length={6} onComplete={handleLogin} />
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
