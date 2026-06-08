import sys
import json
from pathlib import Path

# backend/ 를 sys.path 에 추가해서 app.core 모듈을 바로 import 할 수 있게 합니다.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.opensearch import (
    FINANCIAL_DOCS_INDEX,
    create_indices_if_not_exists,
    get_os_client,
)
from app.core.nlp import tokenize_korean

def seed_bok_terms() -> None:
    """financial_docs 인덱스에 추출된 한국은행 경제금융용어 800선을 색인합니다."""
    json_path = Path(__file__).resolve().parent.parent / "financial_terms.json"
    
    if not json_path.exists():
        print(f"Error: {json_path} 파일이 존재하지 않습니다.")
        return
        
    with open(json_path, "r", encoding="utf-8") as f:
        terms = json.load(f)
        
    client = get_os_client()
    print(f"총 {len(terms)}개의 용어를 색인합니다...")
    
    # Bulk insert 대신 간단하게 반복문 사용 (데이터가 800개 수준이므로 충분히 빠름)
    for i, doc in enumerate(terms, start=1):
        # 파이썬 형태소 분석기로 토큰 추출
        doc["title_tokens"] = tokenize_korean(doc["title"])
        doc["content_tokens"] = tokenize_korean(doc["content"])
        
        # OpenSearch의 기존 문서들과 ID가 겹치지 않도록 'bok_' 접두사를 붙입니다.
        doc_id = f"bok_{i}"
        client.index(index=FINANCIAL_DOCS_INDEX, id=doc_id, body=doc)
        if i % 100 == 0:
            print(f"  진행률: {i}/{len(terms)} 색인 완료")
            
    print(f"✅ 색인 완료: 총 {len(terms)}건")

def main() -> None:
    print("=== OpenSearch 초기화 ===")
    create_indices_if_not_exists()
    print(f"인덱스 준비 완료: {FINANCIAL_DOCS_INDEX}")

    print("\n=== 한국은행 경제금융용어 800선 색인 시작 ===")
    seed_bok_terms()

    client = get_os_client()
    client.indices.refresh(index=FINANCIAL_DOCS_INDEX)
    print("\n완료. 이제 테스트를 진행할 수 있습니다.")

if __name__ == "__main__":
    main()
