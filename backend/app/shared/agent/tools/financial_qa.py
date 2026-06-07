from langchain_core.tools import tool
from opensearchpy import OpenSearchException

from app.core.opensearch import get_os_client, FINANCIAL_DOCS_INDEX
from app.core.exception import OpenSearchError


@tool
def search_financial_docs(query: str, user_id: str) -> str:
    """금융 FAQ를 OpenSearch financial_docs 인덱스에서 검색합니다.

    Args:
        query: 사용자의 질문 내용.
        user_id: JWT에서 추출한 사용자 ID. (모든 툴의 공통 필수 파라미터)

    Returns:
        검색된 FAQ 내용을 결합한 문자열. 검색 결과가 없으면 안내 메시지 반환.

    Raises:
        OpenSearchError: OpenSearch 검색 중 예기치 않은 오류가 발생한 경우.
    """
    client = get_os_client()
    try:
        result = client.search(
            index=FINANCIAL_DOCS_INDEX,
            body={
                "query": {
                    "multi_match": {"query": query, "fields": ["title^2", "content"]}
                },
                "size": 3,
            },
        )
    except OpenSearchException as e:
        raise OpenSearchError(
            code="SEARCH_FAILED",
            message="금융 FAQ 검색 중 오류가 발생했습니다.",
        ) from e

    hits = [h["_source"]["content"] for h in result["hits"]["hits"]]
    if not hits:
        return "해당 내용을 찾을 수 없습니다. 우리은행 고객센터(1588-xxxx)로 문의해 주세요."

    return "\n".join(hits[:3])
