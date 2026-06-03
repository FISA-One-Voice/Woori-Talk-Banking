import { ResultScreen } from '@/components/feedback';
import { ActionButton, SummaryBox } from '@/components/display';

interface CompleteMemoDoneViewProps {
  category: string;
  onGoHome: () => void;
}

export function CompleteMemoDoneView({ category, onGoHome }: CompleteMemoDoneViewProps) {
  return (
    <>
      <ResultScreen type="success" label="메모 저장 완료" />
      <SummaryBox rows={[{ label: '카테고리', value: category }]} />
      <ActionButton label="홈으로 돌아가기" variant="outline" onPress={onGoHome} />
    </>
  );
}
