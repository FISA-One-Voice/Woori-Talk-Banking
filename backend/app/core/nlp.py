from kiwipiepy import Kiwi, Token

# Kiwi 형태소 분석기 초기화
kiwi = Kiwi()

# 검색에 유의미한 품사 목록 (명사, 동사, 형용사, 부사, 외국어, 한자, 숫자)
# 참고: N(명사류), V(동사/형용사류), M(부사/관형사류), SL(알파벳), SH(한자), SN(숫자)
VALID_POS_TAGS = {
    "NNG", "NNP", "NNB", "NR", "NP",  # 명사, 대명사, 수사
    "VV", "VA", "VX",                 # 동사, 형용사, 보조용언
    "MAG", "MAJ", "MM",               # 부사, 관형사
    "SL", "SH", "SN"                  # 외국어(알파벳), 한자, 숫자
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
            result_words.append(word)
            
            # 동의어가 있다면 함께 추가
            if word in SYNONYMS:
                result_words.extend(SYNONYMS[word])
                
    return " ".join(result_words)
