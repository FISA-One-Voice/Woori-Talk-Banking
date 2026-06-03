import { SessionTimer, ResultScreen } from '@/components/feedback';
import { ActionButton, SummaryBox } from '@/components/display';
import { COLORS, FONT_SIZES, LAYOUT } from '@/constants/theme';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';

const MEMO_CATEGORIES = ['식비', '교통비', '쇼핑', '의료비', '문화생활', '기타'];

const MEMO_HINT =
  '음성으로 카테고리를 말씀하시거나, 아래 버튼을 눌러 선택할 수 있습니다.';

interface CompleteSummaryViewProps {
  summaryRows: Array<{ label: string; value: string; variant?: 'yellow' }>;
  onMemoSave: (category: string) => void;
  onSkip: () => void;
}

export function CompleteSummaryView({
  summaryRows,
  onMemoSave,
  onSkip,
}: CompleteSummaryViewProps) {
  return (
    <>
      <ResultScreen type="success" label="송금 완료" />
      <SummaryBox rows={summaryRows} />
      <Text style={styles.hint} accessibilityRole="text">
        {MEMO_HINT}
      </Text>
      <View style={styles.categoryGrid}>
        {MEMO_CATEGORIES.map((cat) => (
          <TouchableOpacity
            key={cat}
            style={styles.categoryBtn}
            onPress={() => onMemoSave(cat)}
            accessibilityRole="button"
            accessibilityLabel={`${cat} 카테고리로 메모 저장`}
          >
            <Text style={styles.categoryText}>{cat}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <SessionTimer onExpire={onSkip} />
      <ActionButton label="건너뛰기" variant="outline" onPress={onSkip} />
    </>
  );
}

const styles = StyleSheet.create({
  hint: {
    fontSize: FONT_SIZES.caption,
    color: COLORS.grayMedium,
    lineHeight: 24,
  },
  categoryGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginVertical: 8,
  },
  categoryBtn: {
    width: '47%',
    paddingVertical: 18,
    backgroundColor: COLORS.surfaceLight,
    borderRadius: LAYOUT.borderRadius,
    borderWidth: 1,
    borderColor: COLORS.border,
    alignItems: 'center',
  },
  categoryText: {
    fontSize: FONT_SIZES.body,
    color: COLORS.textMain,
    fontWeight: '600',
  },
});
