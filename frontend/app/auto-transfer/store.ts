import { create } from 'zustand';

interface AutoTransferFlowState {
  fromAccountId: string | null;
  setFromAccountId: (id: string) => void;
  reset: () => void;
}

export const useAutoTransferFlowStore = create<AutoTransferFlowState>((set) => ({
  fromAccountId: null,
  setFromAccountId: (id) => set({ fromAccountId: id }),
  reset: () => set({ fromAccountId: null }),
}));
