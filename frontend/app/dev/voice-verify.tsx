import React, { useState, useRef, useEffect } from 'react';
import { SafeAreaView, StyleSheet, Text, View, Pressable, ActivityIndicator, Alert } from 'react-native';
import { router } from 'expo-router';
import { TopBar } from '@/components/layout';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import { Ionicons } from '@expo/vector-icons';
import { apiClient } from '@/utils/api';
import { Audio } from 'expo-av';

export default function VoiceVerifyScreen() {
  const [step, setStep] = useState<'READY' | 'RECORDING' | 'RESULT'>('READY');
  const [loading, setLoading] = useState(false);
  const [timeLeft, setTimeLeft] = useState(10);
  const [result, setResult] = useState<{ score: number, is_same_speaker: boolean } | null>(null);

  const recordingRef = useRef<Audio.Recording | null>(null);

  useEffect(() => {
    Audio.setAudioModeAsync({
      allowsRecordingIOS: false,
      playsInSilentModeIOS: true,
      playThroughEarpieceAndroid: false,
      staysActiveInBackground: false,
    });
  }, []);

  const startRecording = async () => {
    try {
      await Audio.requestPermissionsAsync();
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
        playThroughEarpieceAndroid: false,
        staysActiveInBackground: false,
      });

      const { recording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY
      );
      recordingRef.current = recording;
      setStep('RECORDING');
      setTimeLeft(10);

      const interval = setInterval(() => {
        setTimeLeft(prev => {
          if (prev <= 1) {
            clearInterval(interval);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);

      setTimeout(async () => {
        clearInterval(interval);
        if (recordingRef.current === recording) {
          const uri = await stopRecording(recording);
          if (uri) await verifyAudio(uri);
        }
      }, 10000);
    } catch (err) {
      console.error(err);
      setStep('READY');
    }
  };

  const forceStop = async () => {
    if (recordingRef.current) {
      const uri = await stopRecording(recordingRef.current);
      if (uri) await verifyAudio(uri);
    }
  };

  const stopRecording = async (recording: Audio.Recording) => {
    try {
      await recording.stopAndUnloadAsync();
      recordingRef.current = null;
      
      // iOS 수화기 버그 방지 핵 (하드 리셋)
      await Audio.setIsEnabledAsync(false);
      await new Promise(resolve => setTimeout(resolve, 100));
      await Audio.setIsEnabledAsync(true);
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: false,
        playsInSilentModeIOS: true,
        playThroughEarpieceAndroid: false,
        staysActiveInBackground: false,
      });

      return recording.getURI();
    } catch (err) {
      return null;
    }
  };

  const verifyAudio = async (uri: string) => {
    setLoading(true);
    setStep('RESULT');
    try {
      const formData = new FormData();
      formData.append('file', {
        uri,
        name: 'verify_voice.wav',
        type: 'audio/wav',
      } as any);

      const response = await apiClient.post('/api/voice/verify', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 60000,
      });
      
      if (response.data.success) {
        setResult(response.data.data);
      } else {
        Alert.alert('검증 실패', response.data.message || '서버 응답 오류');
      }
    } catch (err: any) {
      console.error(err);
      Alert.alert('오류 발생', err.response?.data?.message || '네트워크 또는 서버 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.root}>
      <TopBar variant="back" title="목소리 검증 테스트" onBack={() => router.back()} />
      <View style={styles.pad}>
        
        <Text style={styles.title}>내 목소리 검증하기 🎤</Text>
        <Text style={styles.subtitle}>
          방금 등록한 공식 3분할 음성 모델이{"\n"}나를 얼마나 정확히 알아보는지 확인해 보세요!
        </Text>

        {step === 'READY' && (
          <View style={{ flex: 1, justifyContent: 'center' }}>
            <Pressable style={styles.button} onPress={startRecording}>
              <Text style={styles.buttonText}>테스트 녹음 시작</Text>
            </Pressable>
          </View>
        )}

        {step === 'RECORDING' && (
          <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
            <View style={styles.micCircle}>
              <Ionicons name="mic" size={60} color={COLORS.highlightYellow} />
            </View>
            <Text style={{ color: 'white', fontSize: 24, marginBottom: 20 }}>
              {timeLeft}초 남음
            </Text>
            <Text style={{ color: '#aaa', marginBottom: 40, textAlign: 'center' }}>
              자유롭게 아무 말이나 해보세요.{"\n"}충분하다면 아래 버튼을 눌러 바로 검증하세요.
            </Text>
            <Pressable style={[styles.button, { backgroundColor: '#F87171' }]} onPress={forceStop}>
              <Text style={{ color: '#fff', fontSize: 18, fontWeight: 'bold' }}>녹음 종료 및 검증하기</Text>
            </Pressable>
          </View>
        )}

        {step === 'RESULT' && (
          <View style={{ flex: 1, marginTop: 20 }}>
            {loading ? (
              <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
                <ActivityIndicator size="large" color={COLORS.highlightYellow} />
                <Text style={{ color: '#aaa', marginTop: 20 }}>ASV 서버에서 AI 판별 중...</Text>
              </View>
            ) : result ? (
              <View>
                <View style={[styles.resultBox, { borderColor: result.is_same_speaker ? '#4ADE80' : '#F87171' }]}>
                  <Text style={[styles.resultTitle, { color: result.is_same_speaker ? '#4ADE80' : '#F87171' }]}>
                    공식 음성 검증 결과
                  </Text>
                  <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginVertical: 10 }}>
                    <Text style={{ color: '#aaa', fontSize: 16 }}>판별 결과:</Text>
                    <Text style={{ color: result.is_same_speaker ? '#4ADE80' : '#F87171', fontSize: 16, fontWeight: 'bold' }}>
                      {result.is_same_speaker ? '동일인 일치 ✅' : '타인 (불일치) ❌'}
                    </Text>
                  </View>
                  <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                    <Text style={{ color: '#aaa', fontSize: 16 }}>유사도 점수:</Text>
                    <Text style={{ color: '#fff', fontSize: 24, fontWeight: 'bold' }}>
                      {result.score.toFixed(4)}
                    </Text>
                  </View>
                </View>

                <Pressable style={[styles.button, { marginTop: 40 }]} onPress={() => setStep('READY')}>
                  <Text style={styles.buttonText}>다시 테스트하기</Text>
                </Pressable>
              </View>
            ) : (
              <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
                <Text style={{ color: '#F87171', textAlign: 'center', marginBottom: 20 }}>분석 실패</Text>
                <Pressable style={styles.button} onPress={() => setStep('READY')}>
                  <Text style={styles.buttonText}>처음으로</Text>
                </Pressable>
              </View>
            )}
          </View>
        )}

      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.background },
  pad: { flex: 1, padding: LAYOUT.paddingMedium },
  title: { fontSize: 24, fontWeight: 'bold', color: COLORS.textMain, marginBottom: 10 },
  subtitle: { fontSize: 14, color: '#aaa', lineHeight: 22, marginBottom: 40 },
  button: {
    backgroundColor: COLORS.highlightYellow,
    width: '100%', paddingVertical: 20,
    borderRadius: LAYOUT.borderRadius, alignItems: 'center',
  },
  buttonText: { fontSize: FONT_SIZES.button, color: '#000', fontWeight: '700' },
  micCircle: {
    width: 120, height: 120, borderRadius: 60,
    borderWidth: 2, borderColor: COLORS.highlightYellow,
    justifyContent: 'center', alignItems: 'center', marginBottom: 24,
  },
  resultBox: {
    backgroundColor: '#1E1E1E',
    borderWidth: 2,
    borderRadius: 16,
    padding: 20,
  },
  resultTitle: {
    fontSize: 18, fontWeight: 'bold', marginBottom: 15
  }
});
