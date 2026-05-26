# =============================================================================
# backend/app/core/opensearch.py
#
# [인덱스 구성]
# ├─ financial_docs : RAG 용 금융 지식 문서 (키워드 검색)
# └─ chatbot_logs   : 사용자별 챗봇 대화 이력
#
# [다른 파일과의 관계]
# ├─ config.py  → OPENSEARCH_* 설정값을 가져와 클라이언트 생성에 사용
# └─ main.py    → 서버 시작 시 create_indices_if_not_exists() 호출
# =============================================================================

from collections.abc import Generator
from typing import Any

from opensearchpy import OpenSearch, OpenSearchException

from app.core.config import settings
from app.core.exception import OpenSearchIndexError

FINANCIAL_DOCS_INDEX = "financial_docs"
CHATBOT_LOGS_INDEX = "chatbot_logs"

_FINANCIAL_DOCS_MAPPING: dict[str, Any] = {
    "mappings": {
        "properties": {
            "title": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "content": {"type": "text", "analyzer": "standard"},
            "category": {"type": "keyword"},
            "source": {"type": "keyword"},
            "created_at": {"type": "date"},
        }
    },
}

_CHATBOT_LOGS_MAPPING: dict[str, Any] = {
    "mappings": {
        "properties": {
            "user_id": {"type": "keyword"},
            "session_id": {"type": "keyword"},
            "role": {"type": "keyword"},  # "user" | "assistant"
            "message": {"type": "text", "analyzer": "standard"},
            "timestamp": {"type": "date"},
        }
    },
}

# database.py 의 engine 과 동일한 역할 — 앱 전체가 하나의 연결 공유
_client: OpenSearch | None = None


def _build_client() -> OpenSearch:
    """CA 인증서 유무에 따라 SSL 검증 방식을 분기합니다.

    OPENSEARCH_CA_CERT 가 없으면 verify_certs=False (로컬 개발 환경용).
    Aiven 프로덕션에서는 CA 인증서를 반드시 설정해야 합니다.
    """
    kwargs: dict[str, Any] = {
        "hosts": [{"host": settings.OPENSEARCH_HOST, "port": settings.OPENSEARCH_PORT}],
        "http_auth": (settings.OPENSEARCH_USER, settings.OPENSEARCH_PASSWORD),
        "use_ssl": settings.OPENSEARCH_USE_SSL,
        "verify_certs": bool(settings.OPENSEARCH_CA_CERT),
        "ssl_show_warn": False,
    }
    if settings.OPENSEARCH_CA_CERT:
        kwargs["ca_certs"] = settings.OPENSEARCH_CA_CERT
    return OpenSearch(**kwargs)


def get_os_client() -> OpenSearch:
    """싱글턴 OpenSearch 클라이언트를 반환합니다.

    Returns:
        연결된 OpenSearch 클라이언트. 최초 호출 시 생성 후 재사용합니다.
    """
    global _client
    if _client is None:
        _client = _build_client()
    return _client


def get_os() -> Generator[OpenSearch, None, None]:
    """FastAPI 의존성 주입용 OpenSearch 클라이언트를 제공합니다.

    Yields:
        OpenSearch: 연결된 클라이언트 객체

    사용 예시:
        def search(q: str, os: OpenSearch = Depends(get_os)):
            return os.search(index=FINANCIAL_DOCS_INDEX, body={...})
    """
    yield get_os_client()


def create_indices_if_not_exists() -> None:
    """financial_docs, chatbot_logs 인덱스가 없으면 생성합니다.

    이미 존재하는 인덱스는 건너뜁니다. (덮어쓰지 않습니다)
    """
    client = get_os_client()
    try:
        for index, mapping in [
            (FINANCIAL_DOCS_INDEX, _FINANCIAL_DOCS_MAPPING),
            (CHATBOT_LOGS_INDEX, _CHATBOT_LOGS_MAPPING),
        ]:
            if not client.indices.exists(index=index):
                client.indices.create(index=index, body=mapping)
    except OpenSearchException as e:
        raise OpenSearchIndexError(
            code="INDEX_CREATION_FAILED",
            message="OpenSearch 인덱스 생성에 실패했습니다.",
        ) from e
