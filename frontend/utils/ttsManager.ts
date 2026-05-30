// =============================================================================
// utils/ttsManager.ts
//
// 앱 전체 expo-speech TTS를 한 곳에서 관리합니다.
//
// [속도 설정]
//   TTS_RATE — Speech.speak의 rate. 1.0 = 기본 속도. 여기서만 바꾸면 된다.
//
// [함수]
//   speakText(msg, opts?) — 모든 expo-speech 호출은 이 함수를 경유한다.
//   registerSound(sound)  — expo-av Sound 인스턴스를 등록한다.
//   stopAllTts()          — 재생 중인 모든 TTS(expo-speech + expo-av)를 중단한다.
// =============================================================================

import { Audio } from 'expo-av';
import * as Speech from 'expo-speech';

// ── TTS 속도 ──────────────────────────────────────────────────────────────────

/** expo-speech 재생 속도. 1.0 = 기본. 앱 전체 속도는 여기서만 수정한다. */
export const TTS_RATE = 1.4;

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
    rate: TTS_RATE,
    ...opts,
  });
}

// ── expo-av Sound 추적 ────────────────────────────────────────────────────────

let _sound: Audio.Sound | null = null;

/** expo-av Sound 인스턴스를 등록합니다. 재생 시작 직전에 호출하세요. */
export function registerSound(sound: Audio.Sound | null): void {
  _sound = sound;
}

/** 재생 중인 모든 TTS(expo-speech + expo-av)를 중단합니다. */
export async function stopAllTts(): Promise<void> {
  Speech.stop();
  if (_sound) {
    await _sound.stopAsync().catch(() => undefined);
    _sound = null;
  }
}
