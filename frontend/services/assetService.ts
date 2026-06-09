import { apiClient, ApiResponse } from '@/utils/api';

export interface AccountItem {
  account_id: string;
  bank_name: string;
  account_type: string;
  alias: string | null;
  balance: number;
  is_primary: boolean;
}

export interface AssetSummary {
  accounts: AccountItem[];
  total_asset: number;
  tts_text: string;
}

export async function fetchAssetSummary(): Promise<AssetSummary> {
  const res = await apiClient.get<ApiResponse<AssetSummary>>('/api/asset/summary');
  if (!res.data.success || !res.data.data) {
    throw new Error(res.data.code ?? 'INTERNAL_ERROR');
  }
  return res.data.data;
}

export interface TransactionItem {
  tx_id: string;
  from_account_id: string;
  to_bank_name: string;
  to_name: string | null;
  amount: number;
  tx_type: string;
  status: string;
  category: string | null;
  memo: string | null;
  created_at: string;
  tts_text: string;
}

export async function fetchTransactionHistory(period: string): Promise<TransactionItem[]> {
  const res = await apiClient.get<ApiResponse<{ transactions: TransactionItem[] }>>(
    `/api/asset/history?period=${encodeURIComponent(period)}`
  );
  if (!res.data.success || !res.data.data) {
    throw new Error(res.data.code ?? 'INTERNAL_ERROR');
  }
  return res.data.data.transactions;
}

export interface CategoryItem {
  category: string;
  amount: number;
}

export interface ExpenseSummary {
  total: number;
  days: number;
  top_categories: CategoryItem[];
}

export async function fetchExpenseSummary(period = '이번달'): Promise<ExpenseSummary> {
  const res = await apiClient.get<ApiResponse<ExpenseSummary>>(
    `/api/asset/expense-summary?period=${encodeURIComponent(period)}`
  );
  if (!res.data.success || !res.data.data) {
    throw new Error(res.data.code ?? 'INTERNAL_ERROR');
  }
  return res.data.data;
}

export interface CompareResult {
  period: string;
  compare_period: string;
  category: string | null;
  period_amount: number;
  compare_amount: number;
  diff: number;
}

export async function fetchExpenseCompare(
  period = '이번달',
  comparePeriod = '지난달',
  category?: string,
): Promise<CompareResult> {
  const params = new URLSearchParams({ period, compare_period: comparePeriod });
  if (category) params.append('category', category);
  const res = await apiClient.get<ApiResponse<CompareResult>>(`/api/asset/compare?${params}`);
  if (!res.data.success || !res.data.data) {
    throw new Error(res.data.code ?? 'INTERNAL_ERROR');
  }
  return res.data.data;
}
