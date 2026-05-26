import { useState } from 'react';
import { SafeAreaView, StyleSheet, Text, TextInput, View, Pressable, Alert, Keyboard } from 'react-native';
import { router } from 'expo-router';
import { TopBar } from '@/components/layout';
import { AccessibleNumKeypad } from '@/components/input';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';

export default function DevLoginScreen() {
  const [phone, setPhone] = useState('');
  // AccessibleNumKeypad는 내부적으로 상태를 관리하므로 별도 state 불필요
  
  const handlePhoneChange = (text: string) => {
    const cleaned = text.replace(/[^0-9]/g, ''); // 숫자만 남기기
    let formatted = cleaned;
    
    if (cleaned.length <= 3) {
      formatted = cleaned;
    } else if (cleaned.length <= 7) {
      formatted = `${cleaned.slice(0, 3)}-${cleaned.slice(3)}`;
    } else {
      formatted = `${cleaned.slice(0, 3)}-${cleaned.slice(3, 7)}-${cleaned.slice(7, 11)}`;
    }
    
    setPhone(formatted);

    // 11자리 번호가 꽉 차서 하이픈 포함 13자리가 되면 자동으로 키보드 내림
    if (formatted.length === 13) {
      Keyboard.dismiss();
    }
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
          <Text style={styles.label}>전화번호</Text>
          <TextInput
            style={styles.input}
            value={phone}
            onChangeText={handlePhoneChange}
            keyboardType="phone-pad"
            returnKeyType="done"
            maxLength={13}
            onSubmitEditing={() => Keyboard.dismiss()}
            placeholder="010-0000-0000"
            placeholderTextColor={COLORS.grayMedium}
            accessibilityLabel="전화번호 입력창"
          />

          <View style={{ marginTop: 24, marginBottom: 12 }}>
            <Text style={styles.label}>PIN 번호 (6자리)</Text>
            <Text style={styles.subLabel}>번호를 모두 입력하면 자동으로 로그인됩니다.</Text>
          </View>
          
          <AccessibleNumKeypad 
            length={6} 
            onComplete={handleLogin} 
          />
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
  input: {
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: LAYOUT.borderRadius,
    padding: 16,
    fontSize: FONT_SIZES.title,
    color: '#FFF080', // 기존 노란색보다 눈이 편안한 연한 노란색
  },
});
