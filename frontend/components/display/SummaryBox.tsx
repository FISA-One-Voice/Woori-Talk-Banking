import { StyleSheet, Text, View } from 'react-native';

type RowVariant = 'default' | 'yellow' | 'ok' | 'error';

interface SummaryRow {
  label: string;
  value: string;
  variant?: RowVariant;
}

interface SummaryBoxProps {
  rows: SummaryRow[];
}

const ROW_VALUE_COLOR: Record<RowVariant, string> = {
  default: '#fff',
  yellow: '#FFD600',
  ok: '#4ade80',
  error: '#f87171',
};

export default function SummaryBox({ rows }: SummaryBoxProps) {
  return (
    <View style={styles.box}>
      {rows.map((row, i) => (
        <View
          key={i}
          style={[styles.row, i < rows.length - 1 && styles.rowBorder]}
        >
          <Text style={styles.label}>{row.label}</Text>
          <Text style={[styles.value, { color: ROW_VALUE_COLOR[row.variant ?? 'default'] }]}>
            {row.value}
          </Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    backgroundColor: '#1a1a1a',
    borderWidth: 0.5,
    borderColor: '#252525',
    borderRadius: 8,
    paddingVertical: 4,
    paddingHorizontal: 12,
    marginBottom: 10,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
  },
  rowBorder: {
    borderBottomWidth: 0.5,
    borderBottomColor: '#1e1e1e',
  },
  label: {
    fontSize: 24,
    color: '#555',
  },
  value: {
    fontSize: 28,
    fontWeight: '500',
  },
});

