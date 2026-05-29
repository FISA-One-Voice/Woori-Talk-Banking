# 전역 상태 관리 및 API 통신 가이드라인 (Zustand + Axios)

프론트엔드 **Zustand와 Axios(apiClient)**를 결합하는 방식

---

## 1. 아키텍처 핵심 요약

* **API 통신**: `utils/api.ts`에 정의된 **`apiClient`** (Axios 인스턴스)를 사용합니다. 기본 `fetch` 사용은 금지합니다.
* **인증 토큰(JWT)**: `apiClient` 내부에 **인터셉터(Interceptor)**가 있습니다. 토큰을 신경 쓰지 않아도, API 요청을 보낼 때 `authStore`에서 토큰을 꺼내 헤더에 **자동으로 첨부**해 줍니다.
* **상태 분리**: 도메인이 다르면 스토어(`store`)도 분리합니다. (예: `authStore.ts`, `eventStore.ts`, `transferStore.ts`)

---

## 2. API 호출 방법

새로운 화면에서 백엔드로 데이터를 보낼 때

**새로운 방식 (apiClient 사용)**
```typescript
import { apiClient, ApiResponse } from '@/utils/api';

const handleTransfer = async () => {
  try {
    const response = await apiClient.post<ApiResponse>('/transfer', { amount: 10000 });
    
    if (response.data.success) {
      console.log('송금 성공!');
    }
  } catch (error) {
    console.error('API 에러 발생', error);
  }
};
```

---

## 3. 새로운 도메인 스토어(Store) 만드는 법

만약 이벤트, 송금, 대출과 같은 새로운 기능이 추가된다면, `authStore.ts`에 코드를 넣지 말고 **새로운 스토어 파일**을 만들어주세요.

**`store/transferStore.ts` 예시:**
```typescript
import { create } from 'zustand';
import { apiClient } from '@/utils/api';

interface TransferState {
  status: 'idle' | 'loading' | 'success';
  sendMoney: (amount: number) => Promise<void>;
}

export const useTransferStore = create<TransferState>((set) => ({
  status: 'idle',

  sendMoney: async (amount) => {
    set({ status: 'loading' });
    try {
      // 💡 여기서도 apiClient만 부르면 끝!
      await apiClient.post('/transfer', { amount });
      set({ status: 'success' });
    } catch (error) {
      set({ status: 'idle' });
    }
  }
}));
```

---

## 4. 프론트엔드 라우팅 가드 
서버로 API를 쏘기 전에, 화면 진입 시점이나 버튼 클릭 시점에 **로그인 상태인지 1차로 가볍게 확인**하고 싶을 때는 `authStore.getState().token`을 활용하세요.

```typescript
import { useAuthStore } from '@/store/authStore';

const handleAction = () => {
  const token = useAuthStore.getState().token;
  
  if (!token) {
    Alert.alert('로그인 필요', '이 기능을 사용하려면 로그인해주세요.');
    router.push('/login');
    return; // API 쏘기 전에 컷!
  }
  
  // 토큰이 있으면 로직 진행
};
```

---

