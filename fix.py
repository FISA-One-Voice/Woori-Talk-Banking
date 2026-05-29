import re

with open("frontend/app/dev/voice-register.tsx", "r", encoding="utf-8", errors="replace") as f:
    content = f.read()

# The corrupted block starts at "// 화면 단계에 따른 TTS(음성 읽어주기) 및 자동 전환 제어"
# And ends at "}, [step, recordCount]);\n\n  // 녹음 단계 진입 시 마이크 켜기"

good_block = """  // 화면 단계에 따른 TTS(음성 읽어주기) 및 자동 전환 제어
  useEffect(() => {
    Speech.stop();

    if (step === 'TUTORIAL') {
      Speech.speak("목소리 등록을 시작합니다. 주의사항. 1. 조용한 환경에서 진행해 주세요. 2. 안내 음성 후 삐 소리가 나면 문장을 소리내어 읽어주세요. 3. 정확한 인식을 위해 총 3회 반복합니다. 준비가 되셨다면 화면 하단의 시작하기 버튼을 눌러주세요.", { language: 'ko-KR', rate: 0.9 });
    } else if (step === 'READY') {
      const message = recordCount === 1 
        ? "내 목소리가 나의 비밀번호입니다 라고 말씀해 주세요."
        : `${recordCount}회차 녹음입니다. 다시 한 번 말씀해 주세요.`;

      Speech.speak(message, {
        language: 'ko-KR',
        rate: 0.9,
        onDone: () => {
          setTimeout(() => {
            Speech.speak("삐", { 
              language: 'ko-KR', 
              pitch: 1.5, 
              rate: 1.5,
              onDone: () => {
                setTimeout(() => {
                  setStep('RECORDING');
                }, 1500);
              }
            });
          }, 500);
        },
        onError: () => {
          setTimeout(() => setStep('RECORDING'), 1500);
        }
      });
    } else if (step === 'SUCCESS') {
      Speech.speak("성공적으로 등록되었습니다. 이제 목소리로 간편하게 인증할 수 있습니다.", { language: 'ko-KR', rate: 0.9 });
    } else if (step === 'FAIL') {
      Speech.speak("목소리 인식에 실패했습니다. 조용한 곳에서 다시 시도해 주세요.", { language: 'ko-KR', rate: 0.9 });
    }

    return () => {
      Speech.stop();
    };
  }, [step, recordCount]);"""

pattern = re.compile(r"  // 화면 단계에 따른 TTS.*?\}, \[step, recordCount\]\);", re.DOTALL)
new_content = pattern.sub(good_block, content)

with open("frontend/app/dev/voice-register.tsx", "w", encoding="utf-8") as f:
    f.write(new_content)

print("Fixed!")
