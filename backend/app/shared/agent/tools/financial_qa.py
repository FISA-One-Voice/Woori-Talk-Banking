from langchain_core.tools import tool

from app.features.financial.service import fetch_financial_docs


@tool
def search_financial_docs(query: str, user_id: str) -> str:
    """금융 FAQ를 OpenSearch financial_docs 인덱스에서 검색합니다.

    Args:
        query: 사용자의 질문 내용.
        user_id: JWT에서 추출한 사용자 ID. (모든 툴의 공통 필수 파라미터)

    Returns:
        검색된 FAQ 내용을 결합한 문자열. 검색 결과가 없으면 안내 메시지 반환.
    """
    return fetch_financial_docs(query)
