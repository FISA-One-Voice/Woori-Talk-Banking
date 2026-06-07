from datetime import datetime, timedelta

import httpx
from langchain_core.tools import tool

from app.core.config import settings


@tool
def get_exchange_rate(currency: str, user_id: str) -> str:
    """특정 통화의 현재 환율 정보를 조회합니다.
    
    Args:
        currency: 조회할 통화 코드 또는 이름 (예: USD, 달러, JPY, 엔화 등)
        user_id: JWT에서 추출한 사용자 ID. (모든 툴의 공통 필수 파라미터)
        
    Returns:
        해당 통화의 환율 정보를 포함한 문자열.
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
        # 주말을 고려하여 최근 10일치 데이터를 조회 후 가장 최신(마지막) 데이터 반환
        end_date = datetime.now()
        start_date = end_date - timedelta(days=10)
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")
        
        # 731Y001: 주요국통화의 대원화 환율 (D: 일일)
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


@tool
def get_base_rate(country: str, user_id: str) -> str:
    """특정 국가의 현재 기준 금리를 조회합니다.
    
    Args:
        country: 조회할 국가명 (예: 한국, 미국, 유럽 등)
        user_id: JWT에서 추출한 사용자 ID. (모든 툴의 공통 필수 파라미터)
        
    Returns:
        해당 국가의 기준 금리 정보를 포함한 문자열.
    """
    api_key = settings.BOK_ECOS_API_KEY
    if not api_key:
        return "한국은행 API 키가 설정되지 않았습니다."

    country_lower = country.lower()

    try:
        if country_lower in ["한국", "대한민국", "korea"]:
            # 한국 금리: 722Y001 (일일)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=10)
            start_str = start_date.strftime("%Y%m%d")
            end_str = end_date.strftime("%Y%m%d")
            
            # 0101000: 한국은행 기준금리
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
            # 주요국 정책금리: 902Y006 (월간)
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
                
            # 월간 데이터이므로 주말/시차 대비 넉넉하게 최근 3개월 조회 후 최신값(마지막 값) 반환
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
