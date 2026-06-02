import * as Contacts from 'expo-contacts';
import { Alert } from 'react-native';
import { apiClient } from './api';

export async function syncDeviceContactsToBackend() {
  try {
    const { status } = await Contacts.requestPermissionsAsync();
    
    if (status !== 'granted') {
      Alert.alert('권한 거부', '연락처 접근 권한이 필요합니다.');
      return;
    }

    // 디바이스 연락처 가져오기 (전화번호가 있는 것만)
    const { data } = await Contacts.getContactsAsync({
      fields: [Contacts.Fields.PhoneNumbers],
    });

    if (data.length > 0) {
      // [{ name: "홍길동", phone: "010-1234-5678" }, ...] 형태로 매핑
      const contactsToSend = data
        .filter((c) => c.phoneNumbers && c.phoneNumbers.length > 0)
        .map((c) => ({
          name: c.name || '알 수 없음', // 이름이 없는 연락처 예외 처리
          phone: c.phoneNumbers![0].number || '',
        }))
        .filter((c) => c.phone !== ''); // 번호가 빈 문자열인 경우도 최종 필터링

      // 서버로 전송
      const response = await apiClient.post('/api/contacts/sync', {
        contacts: contactsToSend,
      });

      const addedCount = response.data.data?.addedCount || 0;
      Alert.alert('동기화 완료', `${addedCount}명의 연락처가 우리톡뱅킹에 자동 등록되었습니다!`);
    } else {
      Alert.alert('연락처 없음', '디바이스에 저장된 연락처가 없습니다.');
    }
  } catch (error) {
    console.error('연락처 동기화 에러:', error);
    Alert.alert('오류', '연락처 동기화 중 문제가 발생했습니다.');
  }
}
