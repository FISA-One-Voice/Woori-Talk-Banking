import { StyleSheet, View } from 'react-native';
import TopBar from './TopBar';
import { COLORS } from '@/constants/theme';

export default function AppScreenHeader() {
  return (
    <View style={styles.wrap}>
      <TopBar variant="logo" />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    borderBottomWidth: 0.5,
    borderBottomColor: COLORS.surfaceLight,
    marginBottom: 8,
  },
});
