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

export interface RecentRecipientsResult {
  recipients: RecipientItem[];
  tts_audio_base64: string | null;
}

export async function fetchRecentRecipients(): Promise<RecentRecipientsResult> {
  const res = await apiClient.get<ApiResponse<RecentRecipientsResult>>(
    '/api/transfer/recent',
  );
  return {
    recipients: res.data.data?.recipients ?? [],
    tts_audio_base64: res.data.data?.tts_audio_base64 ?? null,
  };
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
