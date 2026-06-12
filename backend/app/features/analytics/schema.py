from pydantic import BaseModel


class CategorySpending(BaseModel):
    """카테고리별 지출 단건.

    Attributes:
        category: 카테고리명. 예: "식비", "교통", "쇼핑".
        amount: 해당 카테고리 총 지출액 (원).
        ratio: 전체 지출 대비 비율 (%). 예: 42.8.
    """

    category: str
    amount: int
    ratio: float


class MonthlyAnalyticsResponse(BaseModel):
    """GET /api/analytics/monthly 응답.

    프론트엔드 리포트 화면(report/index.tsx)에서 차트를 그리는 데 필요한
    월별 지출 분석 데이터를 담습니다.
    """

    period: str
    total_spending: int
    categories: list[CategorySpending]
    top_category: str
