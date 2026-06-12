# =============================================================================
# backend/app/core/nlp.py
#
# [이 파일의 역할]
# RAG 검색 고도화를 위해 한국어 자연어 처리(형태소 분석 및 불용어 제거)를 수행합니다.
# 사용자의 검색어나 오픈서치 DB 문서에서 의미 없는 조사, 대명사, 보조용언 등을 걷어내고
# 오직 핵심 명사와 동사(키워드)만 추출하여 오픈서치(BM25)의 검색 정확도를 극대화합니다.
#
# [다른 파일과의 관계]
# ├─ features/financial/service.py → 사용자 질문에서 핵심 키워드를 추출할 때 호출됩니다.
# └─ (스크립트) reindex_tokens.py  → DB에 저장된 기존 문서의 토큰을 최신화할 때 사용됩니다.
# =============================================================================

from kiwipiepy import Kiwi, Token

# Kiwi 형태소 분석기 초기화
kiwi = Kiwi()

# 검색에 유의미한 품사 목록 (명사, 동사, 형용사, 부사, 외국어, 한자, 숫자)
# NNB(의존명사), NP(대명사), VX(보조용언), MM(관형사) 제거
VALID_POS_TAGS = {
    "NNG", "NNP", "NR",               # 일반명사, 고유명사, 수사
    "VV", "VA", "VV-I", "VV-R", "VA-I", "VA-R",  # 동사, 형용사 (불규칙/규칙 포함)
    "MAG", "MAJ",                     # 일반부사, 접속부사
    "SL", "SH", "SN"                  # 외국어(알파벳), 한자, 숫자
}

# 수동 불용어 사전 (품사 필터를 뚫고 들어오는 무의미한 단어들)
STOP_WORDS = {
    "있", "없", "않", "이", "그", "저", "것", "수", 
    "등", "및", "따르", "되", "하", "같", "보", "주", 
    "대하", "위하", "관하", "알려주", "알리", "무엇", "뭐", "어떻", "많", "할", "할수", "경우"
}

import json
from pathlib import Path

# 동의어 사전 동적 로드
SYNONYMS = {}
try:
    synonyms_path = Path(__file__).resolve().parent / "synonyms.json"
    if synonyms_path.exists():
        with open(synonyms_path, "r", encoding="utf-8") as f:
            SYNONYMS = json.load(f)
except Exception as e:
    print(f"동의어 사전 로드 실패: {e}")

def tokenize_korean(text: str) -> str:
    """
    텍스트를 입력받아 불용어(조사, 어미, 기호 등)를 제거하고
    유의미한 토큰들만 남겨 띄어쓰기로 연결한 문자열을 반환합니다.
    동의어가 존재할 경우 동의어도 함께 덧붙여 검색률을 높입니다.
    """
    if not text:
        return ""
        
    tokens: list[Token] = kiwi.tokenize(text)
    
    result_words = []
    for t in tokens:
        if t.tag in VALID_POS_TAGS:
            word = t.form.lower()
            
            # 불용어(Stopwords) 필터링
            if word in STOP_WORDS:
                continue
                
            result_words.append(word)
            
            # 동의어가 있다면 함께 추가
            if word in SYNONYMS:
                result_words.extend(SYNONYMS[word])
                
    return " ".join(result_words)
