"""한국은행 ECOS API를 활용한 금융 시장 정보 조회 서비스.
환율 및 기준금리와 같은 외부 거시경제 데이터를 실시간으로 가져옵니다.
"""
from datetime import datetime, timedelta
import httpx
from app.core.config import settings

def fetch_exchange_rate(currency: str) -> str:
    """특정 통화의 최신 일일 환율(매매기준율)을 조회합니다.
    
    한국은행 ECOS의 731Y001 통계표를 찔러 최근 10일 중 가장 최신 데이터를 반환합니다.
    
    Args:
        currency: 조회할 통화명 (예: USD, JPY, EUR 등)
        
    Returns:
        TTS가 읽기에 적합하도록 자연어로 구성된 환율 결과 문자열
    """
    currency_map = {
        "USD": "0000001",
        "미국 달러": "0000001",
        "달러": "0000001",
        "미국달러": "0000001",
        "JPY": "0000002",
        "엔화": "0000002",
        "엔": "0000002",
        "EUR": "0000003",
        "유로": "0000003",
        "유로화": "0000003",
    }
    
    currency_code = currency_map.get(currency.upper())
    if not currency_code:
        return f"죄송합니다. 현재 {currency}에 대한 환율은 한국은행 API에서 지원하지 않거나 인식할 수 없습니다."

    api_key = settings.BOK_ECOS_API_KEY
    if not api_key:
        return "한국은행 API 키가 설정되지 않았습니다."

    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=10)
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")
        
        url = f"http://ecos.bok.or.kr/api/StatisticSearch/{api_key}/json/kr/1/10/731Y001/D/{start_str}/{end_str}/{currency_code}"
        
        with httpx.Client(timeout=5.0) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()
            
            if "StatisticSearch" in data and "row" in data["StatisticSearch"]:
                rows = data["StatisticSearch"]["row"]
                if rows:
                    latest_rate = rows[-1].get("DATA_VALUE")
                    if currency_code == "0000002":
                        return f"현재 {currency} 환율은 100엔당 {latest_rate}원 입니다."
                    return f"현재 {currency} 환율은 1단위당 {latest_rate}원 입니다."
                    
        return "한국은행 API에서 환율 데이터를 찾을 수 없습니다."
    except Exception as e:
        return f"환율 조회 중 오류가 발생했습니다: {str(e)}"

def fetch_base_rate(country: str) -> str:
    """특정 국가의 최신 정책 기준 금리를 조회합니다.
    
    한국은 일일 통계표(722Y001)를, 주요 타국은 월간 통계표(902Y006)를 사용하여
    가장 최신 시점의 기준 금리를 반환합니다.
    
    Args:
        country: 조회할 국가명 (예: 한국, 미국, 일본, 유럽 등)
        
    Returns:
        TTS가 읽기에 적합하도록 자연어로 구성된 금리 결과 문자열
    """
    api_key = settings.BOK_ECOS_API_KEY
    if not api_key:
        return "한국은행 API 키가 설정되지 않았습니다."

    country_lower = country.lower()

    try:
        if country_lower in ["한국", "대한민국", "korea"]:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=10)
            start_str = start_date.strftime("%Y%m%d")
            end_str = end_date.strftime("%Y%m%d")
            
            url = f"http://ecos.bok.or.kr/api/StatisticSearch/{api_key}/json/kr/1/10/722Y001/D/{start_str}/{end_str}/0101000"
            
            with httpx.Client(timeout=5.0) as client:
                response = client.get(url)
                response.raise_for_status()
                data = response.json()
                
                if "StatisticSearch" in data and "row" in data["StatisticSearch"]:
                    rows = data["StatisticSearch"]["row"]
                    if rows:
                        latest_rate = rows[-1].get("DATA_VALUE")
                        return f"현재 대한민국 한국은행 기준 금리는 {latest_rate}% 입니다."
                        
            return "한국은행 API에서 한국 금리 데이터를 찾을 수 없습니다."
            
        else:
            country_map = {
                "미국": "US",
                "usa": "US",
                "유럽": "XM",
                "유로존": "XM",
                "유로": "XM",
                "일본": "JP",
                "japan": "JP",
                "영국": "GB",
                "uk": "GB"
            }
            
            item_code = country_map.get(country_lower)
            if not item_code:
                return f"죄송합니다. 현재 한국은행 API에서 {country}의 금리 조회는 지원하지 않거나 인식할 수 없습니다."
                
            end_date = datetime.now()
            start_date = end_date - timedelta(days=90)
            start_str = start_date.strftime("%Y%m")
            end_str = end_date.strftime("%Y%m")
            
            url = f"http://ecos.bok.or.kr/api/StatisticSearch/{api_key}/json/kr/1/10/902Y006/M/{start_str}/{end_str}/{item_code}"
            
            with httpx.Client(timeout=5.0) as client:
                response = client.get(url)
                response.raise_for_status()
                data = response.json()
                
                if "StatisticSearch" in data and "row" in data["StatisticSearch"]:
                    rows = data["StatisticSearch"]["row"]
                    if rows:
                        latest_rate = rows[-1].get("DATA_VALUE")
                        return f"현재 {country}의 정책 기준 금리는 {latest_rate}% 입니다."
                        
            return f"한국은행 API에서 {country} 금리 데이터를 찾을 수 없습니다."
            
    except Exception as e:
        return f"기준 금리 조회 중 오류가 발생했습니다: {str(e)}"
