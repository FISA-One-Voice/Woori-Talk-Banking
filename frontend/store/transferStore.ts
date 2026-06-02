import { create } from 'zustand';
import type { RecipientItem } from '@/components/display';

export interface TransferReceipt {
  txId: string;
  toName: string;
  toBankName: string;
  amount: number;
}

interface TransferState {
  selectedRecipient: RecipientItem | null;
  amount: number | null;
  txReceipt: TransferReceipt | null;

  setSelectedRecipient: (r: RecipientItem | null) => void;
  setAmount: (a: number | null) => void;
  setTxReceipt: (r: TransferReceipt | null) => void;
  reset: () => void;
}

export const useTransferStore = create<TransferState>((set) => ({
  selectedRecipient: null,
  amount: null,
  txReceipt: null,

  setSelectedRecipient: (selectedRecipient) => set({ selectedRecipient }),
  setAmount: (amount) => set({ amount }),
  setTxReceipt: (txReceipt) => set({ txReceipt }),
  reset: () => set({ selectedRecipient: null, amount: null, txReceipt: null }),
}));
