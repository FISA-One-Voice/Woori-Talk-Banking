// =============================================================================
// frontend/context/MicContext.tsx
//
// [이 파일의 역할]
// 전역 마이크 상태를 관리합니다.
// _layout.tsx 의 Pressable(onLongPress) 이 activateMic() 를 호출하고,
// 어떤 화면에서든 useMic() 훅으로 voiceState 를 읽을 수 있습니다.
// =============================================================================

import {
  createContext,
  ReactNode,
  useContext,
  useRef,
  useState,
} from 'react';

// ── 타입 ──────────────────────────────────────────────────────────────────────

export type VoiceState = 'idle' | 'listening' | 'error';

interface MicContextType {
  voiceState: VoiceState;
  activateMic: () => void;
}

// ── Context ───────────────────────────────────────────────────────────────────

const MicContext = createContext<MicContextType>({
  voiceState: 'idle',
  activateMic: () => {},
});

// ── Provider ──────────────────────────────────────────────────────────────────

export function MicProvider({ children }: { children: ReactNode }) {
  const [voiceState, setVoiceState] = useState<VoiceState>('idle');
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function activateMic(): void {
    if (voiceState !== 'idle') return;

    setVoiceState('listening');

    // TODO: STT 연동 시 여기서 STT 호출로 교체
    // 현재: 3초 listening → 3초 error → idle 시뮬레이션
    timerRef.current = setTimeout(() => {
      setVoiceState('error');
      timerRef.current = setTimeout(() => {
        setVoiceState('idle');
      }, 3000);
    }, 3000);
  }

  return (
    <MicContext.Provider value={{ voiceState, activateMic }}>
      {children}
    </MicContext.Provider>
  );
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useMic(): MicContextType {
  return useContext(MicContext);
}
