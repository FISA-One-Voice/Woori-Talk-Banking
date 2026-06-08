from opensearchpy import OpenSearchException
from app.core.opensearch import get_os_client, FINANCIAL_DOCS_INDEX
from app.core.exception import OpenSearchError
from app.core.nlp import tokenize_korean


def fetch_financial_docs(query: str) -> str:
    """사용자의 질문(query)을 기반으로 오픈서치에서 관련 금융 문서를 검색합니다.
    
    제목(title)에 가중치(^2)를 두어 관련성이 높은 상위 3개 문서를 추출합니다.
    
    Args:
        query: 사용자가 음성으로 발화한 금융 관련 질문
        
    Returns:
        상위 3개의 문서 내용을 결합한 문자열 (TTS 및 LLM 요약용)
        
    Raises:
        OpenSearchError: 오픈서치 연결 또는 검색 실패 시 발생
    """
    client = get_os_client()
    # 질문을 형태소 분석기로 정제 (조사 제거 등)
    tokenized_query = tokenize_korean(query)
    search_term = tokenized_query if tokenized_query else query
    
    try:
        result = client.search(
            index=FINANCIAL_DOCS_INDEX,
            body={
                "query": {
                    "multi_match": {
                        "query": search_term, 
                        "fields": ["title^3", "title_tokens^3", "content", "content_tokens"]
                    }
                },
                "size": 3,
            },
        )
    except OpenSearchException as e:
        raise OpenSearchError(
            code="SEARCH_FAILED",
            message="금융 FAQ 검색 중 오류가 발생했습니다.",
            user_message="금융 정보를 검색하는 중 일시적인 오류가 발생했습니다. 잠시 후 다시 질문해 주세요.",
        ) from e

    hits = [f"[{h['_source']['title']}] {h['_source']['content']}" for h in result["hits"]["hits"]]
    if not hits:
        return "해당 내용을 찾을 수 없습니다. 우리은행 고객센터(1588-xxxx)로 문의해 주세요."

    return "\n".join(hits[:3])
