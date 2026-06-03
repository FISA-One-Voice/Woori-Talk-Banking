import { create } from 'zustand';

export interface AutoTransferReceipt {
  orderId: string;
  recipient: string;
  amount: number;
  cycle: string;
  scheduledDay: number | null;
  scheduledDow: number | null;
  bankName: string;
}

interface AutoTransferFlowState {
  fromAccountId: string | null;
  receipt: AutoTransferReceipt | null;
  setFromAccountId: (id: string) => void;
  setReceipt: (r: AutoTransferReceipt | null) => void;
  reset: () => void;
}

export const useAutoTransferFlowStore = create<AutoTransferFlowState>((set) => ({
  fromAccountId: null,
  receipt: null,
  setFromAccountId: (id) => set({ fromAccountId: id }),
  setReceipt: (receipt) => set({ receipt }),
  reset: () => set({ fromAccountId: null, receipt: null }),
}));
