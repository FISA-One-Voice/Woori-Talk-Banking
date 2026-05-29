# Design Ref: §3.4 — Phase 2 개발자용 tool 작성 가이드. ALL_TOOLS에 등록하지 않음.
"""[가이드 파일] 신규 tool 작성 방법 — 실제 운영에 사용되지 않습니다.

이 파일의 목적:
    Phase 2에서 각 화면을 담당하는 개발자가 자신의 tool을 작성할 때
    참고할 수 있는 패턴과 주석을 제공합니다.

    실제 tool 파일은 tools/ 디렉터리에 별도 파일로 작성하고
    tools/__init__.py 의 ALL_TOOLS 리스트에 등록하십시오.

tool이 에이전트와 연결되는 흐름:
    1. features/balance/service.py 에 비즈니스 로직 작성 (TTS 문자열 반환)
    2. tools/balance.py 에서 service 함수를 import 하고 @tool 로 래핑
    3. tools/__init__.py 의 ALL_TOOLS 에 추가
    4. 에이전트가 사용자 발화를 분석해 적절한 tool 자동 선택·실행
"""

# ── 필수 import ────────────────────────────────────────────────────────────────

from langchain_core.tools import tool  # @tool 데코레이터 — LangChain 표준

from app.core.database import get_db

# 자신의 feature service 를 import 합니다:
# from app.features.balance.service import get_balance_text


# ── @tool 데코레이터 기본 패턴 ─────────────────────────────────────────────────
#
# 비즈니스 로직은 service.py 에 작성하고, tool 은 @tool 로 래핑한 뒤
# DB 세션을 직접 생성하여 service 함수에 전달합니다.
#
# db 를 tool 파라미터로 선언하지 마십시오.
# @tool 파라미터는 LLM이 슬롯으로 채우려 하므로 user_id 와 슬롯 값만 포함해야 합니다.


@tool
def sample_get_balance(user_id: str) -> str:  # noqa: D401
    """사용자의 대표 계좌 잔액을 조회합니다.

    이 docstring은 LLM이 직접 읽습니다. 아래 원칙을 지키십시오:
      1. 첫 줄: 이 tool이 '언제' 호출되어야 하는지 명확하게 서술하십시오.
         예: "잔액 조회를 요청할 때 호출합니다."
      2. 트리거 발화 예시를 포함하면 LLM이 더 정확하게 tool을 선택합니다.
         예: '잔액 얼마야', '돈 얼마 있어', '통장 잔액 알려줘' 등

    Args:
        user_id: JWT에서 추출한 사용자 ID. voice/router.py 가 주입합니다.
                 이 파라미터는 모든 tool에 포함되어야 합니다 (인증 검증용).

    Returns:
        TTS로 읽힐 자연어 문자열.
        반드시 마크다운 없이, 숫자는 한국어로 작성하십시오.
        예: "현재 대표 계좌 잔액은 오십만 원입니다."

    Raises:
        BalanceNotFoundError: 계좌를 찾을 수 없을 때.
        (AppError 서브클래스만 raise — main.py 핸들러가 처리)
    """
    db = next(get_db())
    try:
        return get_balance_text(db, user_id)  # type: ignore[name-defined]
    finally:
        db.close()


# ── 비동기 tool 패턴 ───────────────────────────────────────────────────────────
#
# 외부 API 호출(HTTP 요청 등)이 포함된 service 를 래핑할 때는 async def 를 사용하십시오.
# LangGraph create_react_agent 는 동기·비동기 tool 모두 지원합니다.
#
# @tool
# async def sample_async_tool(user_id: str) -> str:
#     """외부 API를 호출하는 비동기 tool 예시."""
#     db = next(get_db())
#     try:
#         return await exchange_service.get_rate_text(db, user_id)
#     finally:
#         db.close()


# ── tool 등록 체크리스트 ──────────────────────────────────────────────────────
#
# tool 작성 완료 후 아래를 확인하십시오:
#
# [ ] 비즈니스 로직과 TTS 포맷은 features/{name}/service.py 에 작성
# [ ] @tool 데코레이터 적용
# [ ] service 함수를 import 하여 호출하고 반환 (tool 안에 로직 작성 금지)
# [ ] docstring 첫 줄: 이 tool이 언제 호출되는지 명시
# [ ] docstring: 트리거 발화 예시 2~3개 포함
# [ ] Args: user_id 파라미터 포함 (db 는 tool 파라미터로 선언하지 않음)
# [ ] Returns: TTS 친화 자연어 (마크다운 없음, 숫자 한국어)
# [ ] Raises: AppError 서브클래스만 사용
# [ ] tools/__init__.py 의 ALL_TOOLS 에 추가 완료
# [ ] pytest 테스트 작성 완료
