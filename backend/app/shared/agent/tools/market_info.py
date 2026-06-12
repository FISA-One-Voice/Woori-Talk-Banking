from langchain_core.tools import tool

from app.features.market.service import fetch_exchange_rate, fetch_base_rate


@tool
def get_exchange_rate(currency: str, user_id: str) -> str:
    """특정 통화의 현재 환율 정보를 조회합니다.

    Args:
        currency: 조회할 통화 코드 또는 이름 (예: USD, 달러, JPY, 엔화 등)
        user_id: JWT에서 추출한 사용자 ID. (모든 툴의 공통 필수 파라미터)

    Returns:
        해당 통화의 환율 정보를 포함한 문자열.
    """
    return fetch_exchange_rate(currency)


@tool
def get_base_rate(country: str, user_id: str) -> str:
    """특정 국가의 현재 기준 금리를 조회합니다.

    Args:
        country: 조회할 국가명 (예: 한국, 미국, 유럽, 일본 등)
        user_id: JWT에서 추출한 사용자 ID. (모든 툴의 공통 필수 파라미터)

    Returns:
        해당 국가의 기준 금리 정보를 포함한 문자열.
    """
    return fetch_base_rate(country)
