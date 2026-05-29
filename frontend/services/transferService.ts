import { apiClient, type ApiResponse } from '@/utils/api';
import type { RecipientItem } from '@/components/display';
import type { TransferReceipt } from '@/store/transferStore';

interface TransferApiResult {
  txId: string;
  toBankName: string;
  toName: string;
  amount: number;
  status: string;
  createdAt: string;
}

export async function fetchRecentRecipients(): Promise<RecipientItem[]> {
  const res = await apiClient.get<ApiResponse<{ recipients: RecipientItem[] }>>(
    '/api/transfer/recent',
  );
  return res.data.data?.recipients ?? [];
}

export async function saveMemo(txId: string, memo: string): Promise<void> {
  await apiClient.post<ApiResponse>(`/api/transfer/${txId}/memo`, { memo });
}

export async function executeTransfer(
  recipient: RecipientItem,
  amount: number,
): Promise<TransferReceipt> {
  const idempotencyKey = `${recipient.recipientId ?? recipient.accountMasked}-${amount}-${Date.now()}`;
  const res = await apiClient.post<ApiResponse<TransferApiResult>>('/api/transfer/', {
    recipient: '',
    bankName: '',
    amount,
    idempotencyKey,
    recipientName: recipient.toName,
    recipientId: recipient.recipientId ?? null,
  });
  const d = res.data.data!;
  return {
    txId: d.txId,
    toName: d.toName,
    toBankName: d.toBankName,
    amount: d.amount,
  };
}
