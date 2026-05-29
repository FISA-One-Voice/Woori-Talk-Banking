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
}

export async function fetchAssetSummary(): Promise<AssetSummary> {
  const res = await apiClient.get<ApiResponse<AssetSummary>>('/api/asset/summary');
  if (!res.data.success || !res.data.data) {
    throw new Error(res.data.code ?? 'INTERNAL_ERROR');
  }
  return res.data.data;
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

export async function fetchExpenseSummary(days = 30): Promise<ExpenseSummary> {
  const res = await apiClient.get<ApiResponse<ExpenseSummary>>(
    `/api/asset/expense-summary?days=${days}`
  );
  if (!res.data.success || !res.data.data) {
    throw new Error(res.data.code ?? 'INTERNAL_ERROR');
  }
  return res.data.data;
}
