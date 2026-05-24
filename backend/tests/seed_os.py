# =============================================================================
# backend/tests/seed_os.py
#
# [이 파일의 역할]
# financial_docs 인덱스에 샘플 금융 지식 문서를 색인하고
# 키워드 검색 쿼리가 정상 동작하는지 확인합니다.
#
# [실행 방법]
# cd backend
# python -m tests.seed_os
# =============================================================================

import sys
from datetime import datetime, timezone
from pathlib import Path

# backend/ 를 sys.path 에 추가해서 app.core 모듈을 바로 import 할 수 있게 합니다.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.opensearch import (
    CHATBOT_LOGS_INDEX,
    FINANCIAL_DOCS_INDEX,
    create_indices_if_not_exists,
    get_os_client,
)

# ── 샘플 문서 ───────────────────────────────────────────────────────────────────
SAMPLE_DOCS: list[dict[str, str]] = [
    {
        "title": "자동이체 서비스 안내",
        "content": (
            "자동이체는 매월 지정한 날짜에 등록된 계좌에서 자동으로 "
            "출금되는 서비스입니다. 공과금, 보험료, 적금 등 정기 납부에 활용할 수 있습니다. "
            "출금일이 주말 또는 공휴일이면 다음 영업일에 처리됩니다."
        ),
        "category": "자동이체",
        "source": "우리은행 서비스 안내",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    },
    {
        "title": "계좌 이체 한도 및 수수료 안내",
        "content": (
            "인터넷뱅킹 이체 한도는 1회 1억 원, 1일 5억 원입니다. "
            "타행 이체 수수료는 건당 500원이며, 우대 고객은 면제됩니다. "
            "당행 간 이체는 24시간 수수료 없이 이용 가능합니다."
        ),
        "category": "이체",
        "source": "우리은행 서비스 안내",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    },
    {
        "title": "음성 보안 인증 서비스",
        "content": (
            "음성 보안 인증은 고객의 목소리를 등록하여 본인 확인에 활용하는 서비스입니다. "
            "등록된 음성 정보는 암호화하여 안전하게 보관합니다. "
            "음성 인증 실패 시 5회 초과하면 계정이 잠깁니다."
        ),
        "category": "보안인증",
        "source": "우리은행 서비스 안내",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    },
    {
        "title": "예금 금리 안내",
        "content": (
            "정기예금 금리는 가입 기간과 금액에 따라 연 2.5%~4.0% 수준입니다. "
            "12개월 기준 기본 금리는 연 3.5%이며, 우대 조건 충족 시 최대 0.5% 추가됩니다. "
            "만기 자동 해지 및 재예치 서비스를 신청할 수 있습니다."
        ),
        "category": "예금",
        "source": "우리은행 금리 안내",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    },
    {
        "title": "대출 상환 방법 안내",
        "content": (
            "대출 상환 방법에는 원금균등상환, 원리금균등상환, 만기일시상환이 있습니다. "
            "원금균등상환은 매월 동일한 원금을 납부하며, 이자는 잔액에 따라 감소합니다. "
            "중도 상환 시 중도상환수수료가 부과될 수 있습니다."
        ),
        "category": "대출",
        "source": "우리은행 대출 안내",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    },
]


def seed_financial_docs() -> None:
    """financial_docs 인덱스에 샘플 문서를 색인합니다.

    이미 같은 ID 의 문서가 있으면 덮어씁니다 (index API 동작).
    """
    client = get_os_client()
    for i, doc in enumerate(SAMPLE_DOCS, start=1):
        client.index(index=FINANCIAL_DOCS_INDEX, id=str(i), body=doc)
        print(f"  색인 완료 [{i}] {doc['title']}")


def search_financial_docs(keyword: str) -> list[dict[str, str | float]]:
    """financial_docs 인덱스에서 키워드로 문서를 검색합니다.

    title, content 두 필드를 동시에 검색하는 multi_match 쿼리를 사용합니다.

    Args:
        keyword: 검색할 키워드 문자열

    Returns:
        매칭된 문서 목록 (score 내림차순)
    """
    client = get_os_client()
    response = client.search(
        index=FINANCIAL_DOCS_INDEX,
        body={
            "query": {
                "multi_match": {
                    "query": keyword,
                    "fields": ["title^2", "content"],  # title 가중치 2배
                }
            },
            "size": 5,
        },
    )
    hits = response["hits"]["hits"]
    return [
        {
            "score": h["_score"],
            "title": h["_source"]["title"],
            "category": h["_source"]["category"],
            "content": h["_source"]["content"][:80] + "...",
        }
        for h in hits
    ]


def main() -> None:
    print("=== OpenSearch 초기화 ===")
    create_indices_if_not_exists()
    print(f"인덱스 준비 완료: {FINANCIAL_DOCS_INDEX}, {CHATBOT_LOGS_INDEX}")

    print("\n=== financial_docs 샘플 색인 ===")
    seed_financial_docs()

    # refresh 후 검색해야 방금 색인한 문서가 즉시 조회됨
    get_os_client().indices.refresh(index=FINANCIAL_DOCS_INDEX)

    print("\n=== 키워드 검색 확인 ===")
    for keyword in ["자동이체", "음성 인증", "이체 수수료"]:
        results = search_financial_docs(keyword)
        print(f"\n  검색어: '{keyword}' → {len(results)}건")
        for r in results:
            print(f"    [{r['score']:.2f}] {r['title']} ({r['category']})")
            print(f"           {r['content']}")

    print("\n완료.")


if __name__ == "__main__":
    main()
