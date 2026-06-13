// =============================================================================
// utils/ttsManager.ts
//
// 앱 전체 expo-speech TTS를 한 곳에서 관리합니다.
//
// [속도 설정]
//   getTtsRate() — 로그인한 사용자의 tts_speed(DB)를 반환. 미로그인 시 1.7.
//
// [함수]
//   speakText(msg, opts?) — 모든 expo-speech 호출은 이 함수를 경유한다.
//   registerSound(sound)  — expo-av Sound 인스턴스를 등록한다.
//   stopAllTts()          — 재생 중인 모든 TTS(expo-speech + expo-av)를 중단한다.
// =============================================================================

import { useAuthStore } from '@/store/authStore';
import { Audio } from 'expo-av';
import * as Speech from 'expo-speech';

// ── TTS 속도 ──────────────────────────────────────────────────────────────────

/** 현재 로그인한 사용자의 TTS 재생 속도를 반환합니다. 미로그인 시 1.7. */
export function getTtsRate(): number {
  return useAuthStore.getState().ttsSpeed ?? 1.7;
}

// ── expo-speech 래퍼 ──────────────────────────────────────────────────────────

/**
 * 앱 전체 expo-speech TTS 호출 래퍼.
 * language, rate 는 자동 적용되며 추가 옵션은 opts 로 전달한다.
 */
export function speakText(
  message: string,
  opts?: Omit<Speech.SpeechOptions, 'language' | 'rate'>,
): void {
  Speech.speak(message, {
    language: 'ko-KR',
    rate: getTtsRate(),
    volume: 1.0,
    ...opts,
  });
}

// ── expo-av Sound 추적 ────────────────────────────────────────────────────────

let _sound: Audio.Sound | null = null;

export function registerSound(sound: Audio.Sound | null): void {
  _sound = sound;
}

export async function stopAllTts(): Promise<void> {
  Speech.stop();
  if (_sound) {
    await _sound.stopAsync().catch(() => undefined);
    _sound = null;
  }
}

// ── 에이전트 오디오 완료 대기 ──────────────────────────────────────────────────
// _layout.tsx가 에이전트 오디오를 시작하기 전에 startNewAudioSession()을 호출해
// Promise를 세팅한다. 오디오가 끝나면 resolveCurrentAudioEnd()로 완료 신호를 보낸다.
// transfer/index.tsx는 getCurrentAudioEnd()를 await해 최근 수취인 TTS를 직렬 재생한다.

let _audioEndResolve: (() => void) | null = null;
let _audioEndPromise: Promise<void> = Promise.resolve();

export function startNewAudioSession(): void {
  _audioEndPromise = new Promise<void>((resolve) => {
    _audioEndResolve = resolve;
  });
}

export function resolveCurrentAudioEnd(): void {
  _audioEndResolve?.();
  _audioEndResolve = null;
}

export function getCurrentAudioEnd(): Promise<void> {
  return _audioEndPromise;
}
