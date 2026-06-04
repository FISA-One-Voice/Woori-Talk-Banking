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
  receipt: AutoTransferReceipt | null;
  setReceipt: (r: AutoTransferReceipt | null) => void;
  reset: () => void;
}

export const useAutoTransferFlowStore = create<AutoTransferFlowState>((set) => ({
  receipt: null,
  setReceipt: (receipt) => set({ receipt }),
  reset: () => set({ receipt: null }),
}));
