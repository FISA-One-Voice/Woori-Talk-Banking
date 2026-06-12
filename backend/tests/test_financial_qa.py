import pytest
from app.core.opensearch import (
    create_indices_if_not_exists,
    get_os_client,
    FINANCIAL_DOCS_INDEX,
)
from app.shared.agent.tools.financial_qa import search_financial_docs
from tests.seed_os import seed_financial_docs
from app.core.exception import OpenSearchError


@pytest.fixture(scope="module", autouse=True)
def setup_opensearch():
    """테스트 실행 전 실제 OpenSearch 서버에 인덱스를 생성하고 샘플 데이터를 색인합니다."""
    create_indices_if_not_exists()
    seed_financial_docs()
    # 즉시 검색 가능하도록 인덱스 리프레시
    get_os_client().indices.refresh(index=FINANCIAL_DOCS_INDEX)
    yield
    # 필요하다면 teardown 로직을 추가할 수 있습니다.


def test_search_financial_docs_success_real():
    """실제 OpenSearch 서버에 쿼리를 날려 검색 결과가 병합되어 오는지 확인합니다."""
    # seed_os.py에 있는 "자동이체 서비스 안내" 등의 문서가 검색되어야 합니다.
    result = search_financial_docs.invoke({"query": "자동이체", "user_id": "test_user"})

    assert "자동이체는 매월 지정한 날짜에" in result
    assert "출금되는 서비스" in result


def test_search_financial_docs_empty_real():
    """실제 서버에 없는 키워드를 검색했을 때 Fallback 안내 멘트가 나오는지 확인합니다."""
    result = search_financial_docs.invoke(
        {"query": "절대존재하지않는외계인은행", "user_id": "test_user"}
    )

    assert "해당 내용을 찾을 수 없습니다" in result
    assert "1588-xxxx" in result


def test_search_financial_docs_error_real():
    """의도적으로 인덱스를 삭제하여 실제 OpenSearch 예외(NotFoundError) 발생 시
    우리은행 커스텀 예외(OpenSearchError)로 정상 변환되는지 테스트합니다."""
    client = get_os_client()

    # 의도적인 에러 유발을 위해 인덱스 강제 삭제
    if client.indices.exists(index=FINANCIAL_DOCS_INDEX):
        client.indices.delete(index=FINANCIAL_DOCS_INDEX)

    with pytest.raises(OpenSearchError) as exc_info:
        search_financial_docs.invoke(
            {"query": "에러 발생 테스트", "user_id": "test_user"}
        )

    assert exc_info.value.code == "SEARCH_FAILED"

    # 다른 테스트(또는 다음 실행)를 위해 인덱스 원상 복구
    create_indices_if_not_exists()
    seed_financial_docs()
    client.indices.refresh(index=FINANCIAL_DOCS_INDEX)
