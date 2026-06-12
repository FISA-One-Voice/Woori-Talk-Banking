import { apiClient, ApiResponse } from '@/utils/api';

export interface CategorySpending {
  category: string;
  amount: number;
  ratio: number;
}

export interface MonthlyAnalytics {
  period: string;
  total_spending: number;
  categories: CategorySpending[];
  top_category: string;
}

export const ANALYTICS_PERIODS = ['이번달', '지난달', '3개월'] as const;
export type AnalyticsPeriod = (typeof ANALYTICS_PERIODS)[number];

/**
 * GET /api/analytics/monthly — 월별 지출 분석 조회.
 *
 * @param period 조회 기간. "이번달" | "지난달" | "3개월". 기본값 "이번달".
 * @returns MonthlyAnalytics (period, total_spending, categories, top_category).
 * @throws Error(code) 서버 응답 실패 시 code 문자열로 throw.
 */
export async function fetchMonthlyAnalytics(
  period: AnalyticsPeriod = '이번달',
): Promise<MonthlyAnalytics> {
  const res = await apiClient.get<ApiResponse<MonthlyAnalytics>>(
    `/api/analytics/monthly?period=${encodeURIComponent(period)}`,
  );
  if (!res.data.success || !res.data.data) {
    throw new Error(res.data.code ?? 'INTERNAL_ERROR');
  }
  return res.data.data;
}
