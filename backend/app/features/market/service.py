"""한국은행 ECOS API를 활용한 금융 시장 정보 조회 서비스.
환율 및 기준금리와 같은 외부 거시경제 데이터를 실시간으로 가져옵니다.
"""

from datetime import datetime, timedelta
import httpx
from app.core.config import settings
from app.core.exception import MarketError


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
        "CNY": "0000053",
        "위안": "0000053",
        "위안화": "0000053",
        "중국 위안": "0000053",
        "중국위안": "0000053",
        "GBP": "0000012",
        "파운드": "0000012",
        "영국 파운드": "0000012",
        "영국파운드": "0000012",
        "CAD": "0000013",
        "캐나다 달러": "0000013",
        "캐나다달러": "0000013",
        "CHF": "0000014",
        "스위스 프랑": "0000014",
        "스위스프랑": "0000014",
        "HKD": "0000015",
        "홍콩 달러": "0000015",
        "홍콩달러": "0000015",
        "AUD": "0000017",
        "호주 달러": "0000017",
        "호주달러": "0000017",
        "NZD": "0000026",
        "뉴질랜드 달러": "0000026",
        "뉴질랜드달러": "0000026",
        "SGD": "0000024",
        "싱가포르 달러": "0000024",
        "싱가포르달러": "0000024",
        "TWD": "0000031",
        "대만 달러": "0000031",
        "대만달러": "0000031",
        "THB": "0000028",
        "태국 바트": "0000028",
        "태국바트": "0000028",
        "IDR": "0000029",
        "인도네시아 루피아": "0000029",
        "루피아": "0000029",
        "MYR": "0000025",
        "말레이시아 링깃": "0000025",
        "링깃": "0000025",
        "PHP": "0000034",
        "필리핀 페소": "0000034",
        "페소": "0000034",
        "VND": "0000035",
        "베트남 동": "0000035",
        "동": "0000035",
        "INR": "0000037",
        "인도 루피": "0000037",
        "루피": "0000037",
        "MXN": "0000040",
        "멕시코 페소": "0000040",
        "BRL": "0000041",
        "브라질 헤알": "0000041",
        "헤알": "0000041",
        "RUB": "0000043",
        "러시아 루블": "0000043",
        "루블": "0000043",
        "SAR": "0000020",
        "사우디 리얄": "0000020",
        "리얄": "0000020",
        "AED": "0000023",
        "아랍에미리트 디르함": "0000023",
        "디르함": "0000023",
        "TRY": "0000050",
        "터키 리라": "0000050",
        "튀르키예 리라": "0000050",
        "리라": "0000050",
        "ZAR": "0000051",
        "남아공 랜드": "0000051",
        "랜드": "0000051",
        "EGP": "0000052",
        "이집트 파운드": "0000052",
    }

    currency_code = currency_map.get(currency.upper())
    if not currency_code:
        return f"죄송합니다. 현재 {currency}에 대한 환율은 한국은행 API에서 지원하지 않거나 인식할 수 없습니다."

    api_key = settings.BOK_ECOS_API_KEY
    if not api_key:
        raise MarketError(
            code="MISSING_API_KEY",
            message="한국은행 API 키가 설정되지 않았습니다.",
            user_message="시스템 설정 오류로 환율 조회를 할 수 없습니다.",
            status_code=500,
        )

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
                    if currency_code in [
                        "0000002",
                        "0000006",
                        "0000010",
                        "0000029",
                        "0000035",
                    ]:
                        return (
                            f"현재 {currency} 환율은 100단위당 {latest_rate}원 입니다."
                        )
                    return f"현재 {currency} 환율은 1단위당 {latest_rate}원 입니다."

        return "한국은행 API에서 환율 데이터를 찾을 수 없습니다."
    except httpx.HTTPError as e:
        raise MarketError(
            code="MARKET_API_HTTP_ERROR",
            message=f"한국은행 API 통신 중 오류가 발생했습니다: {str(e)}",
            user_message="환율 정보를 불러오는 중 일시적인 네트워크 오류가 발생했습니다.",
            status_code=502,
        ) from e
    except Exception as e:
        raise MarketError(
            code="MARKET_API_FAILED",
            message=f"환율 조회 중 알 수 없는 오류가 발생했습니다: {str(e)}",
            user_message="환율 정보를 처리하는 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            status_code=500,
        ) from e


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
        raise MarketError(
            code="MISSING_API_KEY",
            message="한국은행 API 키가 설정되지 않았습니다.",
            user_message="시스템 설정 오류로 금리 조회를 할 수 없습니다.",
            status_code=500,
        )

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
                        return (
                            f"현재 대한민국 한국은행 기준 금리는 {latest_rate}% 입니다."
                        )

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
                "uk": "GB",
                "호주": "AU",
                "australia": "AU",
                "브라질": "BR",
                "brazil": "BR",
                "캐나다": "CA",
                "canada": "CA",
                "칠레": "CL",
                "chile": "CL",
                "중국": "CN",
                "china": "CN",
                "체코": "CZ",
                "czech": "CZ",
                "덴마크": "DK",
                "denmark": "DK",
                "헝가리": "HU",
                "hungary": "HU",
                "아이슬란드": "IS",
                "iceland": "IS",
                "인도": "IN",
                "india": "IN",
                "인도네시아": "ID",
                "indonesia": "ID",
                "이스라엘": "IL",
                "israel": "IL",
                "멕시코": "MX",
                "mexico": "MX",
                "뉴질랜드": "NZ",
                "new zealand": "NZ",
                "노르웨이": "NO",
                "norway": "NO",
                "폴란드": "PL",
                "poland": "PL",
                "러시아": "RU",
                "russia": "RU",
                "남아프리카공화국": "ZA",
                "남아공": "ZA",
                "south africa": "ZA",
                "스웨덴": "SE",
                "sweden": "SE",
                "스위스": "CH",
                "swiss": "CH",
                "switzerland": "CH",
                "튀르키예": "TR",
                "터키": "TR",
                "turkey": "TR",
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
                        return (
                            f"현재 {country}의 정책 기준 금리는 {latest_rate}% 입니다."
                        )

            return f"한국은행 API에서 {country} 금리 데이터를 찾을 수 없습니다."

    except httpx.HTTPError as e:
        raise MarketError(
            code="MARKET_API_HTTP_ERROR",
            message=f"한국은행 API 통신 중 오류가 발생했습니다: {str(e)}",
            user_message="금리 정보를 불러오는 중 일시적인 네트워크 오류가 발생했습니다.",
            status_code=502,
        ) from e
    except Exception as e:
        raise MarketError(
            code="MARKET_API_FAILED",
            message=f"기준 금리 조회 중 알 수 없는 오류가 발생했습니다: {str(e)}",
            user_message="금리 정보를 처리하는 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            status_code=500,
        ) from e
