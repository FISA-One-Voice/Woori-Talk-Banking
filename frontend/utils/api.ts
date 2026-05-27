import { useAuthStore } from '@/store/authStore';

export function authHeader() {
  const { token } = useAuthStore.getState();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
