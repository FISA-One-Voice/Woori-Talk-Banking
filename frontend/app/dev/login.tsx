import { useState } from 'react';
import { Alert, SafeAreaView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { router } from 'expo-router';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import { apiClient, ApiResponse } from '@/utils/api';
import { useAuthStore } from '@/store/authStore';

export default function DevLoginScreen() {
  const [phone, setPhone] = useState('010-1234-5678');
  const [pin, setPin] = useState('1234');
  const [loading, setLoading] = useState(false);
  const { setTokens } = useAuthStore();

  const handleLogin = async () => {
    setLoading(true);
    try {
      const res = await apiClient.post<ApiResponse<{ accessToken: string; refreshToken: string }>>(
        '/users/login',
        { phone, pin }
      );
      if (res.data.success && res.data.data) {
        setTokens(res.data.data.accessToken, res.data.data.refreshToken);
        Alert.alert('로그인 성공', '토큰이 저장되었습니다.', [
          { text: '홈으로', onPress: () => router.replace('/home') },
        ]);
      } else {
        Alert.alert('실패', res.data.message ?? '로그인 실패');
      }
    } catch {
      Alert.alert('오류', '서버에 연결할 수 없습니다.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.container}>
        <Text style={styles.title}>개발용 로그인</Text>
        <TextInput
          style={styles.input}
          value={phone}
          onChangeText={setPhone}
          placeholder="전화번호"
          placeholderTextColor={COLORS.grayMedium}
          keyboardType="phone-pad"
        />
        <TextInput
          style={styles.input}
          value={pin}
          onChangeText={setPin}
          placeholder="PIN"
          placeholderTextColor={COLORS.grayMedium}
          keyboardType="number-pad"
          secureTextEntry
          maxLength={6}
        />
        <TouchableOpacity style={[styles.btn, loading && { opacity: 0.5 }]} onPress={handleLogin} disabled={loading}>
          <Text style={styles.btnText}>{loading ? '로그인 중...' : '로그인'}</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={() => router.back()}>
          <Text style={styles.back}>← 돌아가기</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.background },
  container: { flex: 1, justifyContent: 'center', padding: LAYOUT.paddingMedium * 2, gap: 16 },
  title: { fontSize: FONT_SIZES.button, color: COLORS.highlightYellow, fontWeight: '700', textAlign: 'center', marginBottom: 16 },
  input: { backgroundColor: COLORS.surface, borderWidth: 1, borderColor: COLORS.border, borderRadius: LAYOUT.borderRadius, padding: 16, fontSize: FONT_SIZES.body, color: COLORS.textMain },
  btn: { backgroundColor: COLORS.highlightYellow, borderRadius: LAYOUT.borderRadius, paddingVertical: 18, alignItems: 'center' },
  btnText: { fontSize: FONT_SIZES.body, fontWeight: '700', color: COLORS.background },
  back: { fontSize: FONT_SIZES.caption, color: COLORS.grayMedium, textAlign: 'center', marginTop: 8 },
});
