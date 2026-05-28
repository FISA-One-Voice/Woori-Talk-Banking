# Design Ref: §3.4 — Phase 2 개발자용 tool 작성 가이드. ALL_TOOLS에 등록하지 않음.
"""[가이드 파일] 신규 tool 작성 방법 — 실제 운영에 사용되지 않습니다.

이 파일의 목적:
    Phase 2에서 각 화면을 담당하는 개발자가 자신의 tool을 작성할 때
    참고할 수 있는 패턴과 주석을 제공합니다.

    실제 tool 파일은 tools/ 디렉터리에 별도 파일로 작성하고
    tools/__init__.py 의 ALL_TOOLS 리스트에 등록하십시오.

tool이 에이전트와 연결되는 흐름:
    1. tools/balance.py 에 @tool 함수 작성
    2. tools/__init__.py 에 import 후 ALL_TOOLS 에 추가
    3. shared/voice/router.py (Issue #7) 가 build_graph(ALL_TOOLS) 호출
    4. 에이전트가 사용자 발화를 분석해 적절한 tool 자동 선택·실행
"""

# ── 필수 import ────────────────────────────────────────────────────────────────

from langchain_core.tools import tool  # @tool 데코레이터 — LangChain 표준

# DB 세션이 필요한 tool의 경우 (대부분의 banking tool):
# from sqlalchemy.orm import Session
# from app.core.database import get_db

# AppError 서브클래스 (CLAUDE.md 규칙):
# from app.core.exception import BalanceNotFoundError, TransferError, ...

# 자신의 feature service:
# from app.features.balance.service import get_primary_balance


# ── @tool 데코레이터 기본 패턴 ─────────────────────────────────────────────────


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
    # ── 실제 구현 예시 (주석 처리) ──────────────────────────────────────────
    # db: Session = next(get_db())
    # balance = get_primary_balance(db, user_id)
    # amount_kor = num_to_korean(balance)  # 숫자 → 한국어 변환 유틸
    # return f"현재 대표 계좌 잔액은 {amount_kor}입니다."
    # ────────────────────────────────────────────────────────────────────────

    # 이 샘플 함수는 실제 로직 없이 반환합니다 (가이드 목적)
    return "샘플 tool입니다. 실제 구현은 tools/balance.py 에 작성하십시오."


# ── 비동기 tool 패턴 ───────────────────────────────────────────────────────────
#
# 외부 API 호출(HTTP 요청 등)이 포함된 tool은 async def 를 사용하십시오.
# LangGraph create_react_agent 는 동기·비동기 tool 모두 지원합니다.
#
# @tool
# async def sample_async_tool(user_id: str) -> str:
#     """외부 API를 호출하는 비동기 tool 예시."""
#     async with httpx.AsyncClient() as client:
#         response = await client.get(...)
#     return response.json()["result"]


# ── DB 세션 주입 패턴 ─────────────────────────────────────────────────────────
#
# tool 내에서 DB 세션을 사용하려면 voice/router.py 에서 세션을 생성하여
# tool 함수에 직접 넘기는 방식을 권장합니다 (FastAPI DI와의 충돌 방지).
#
# 방법 1 — 클로저 패턴 (권장):
#   def make_balance_tool(db: Session):
#       @tool
#       def get_balance(user_id: str) -> str:
#           """잔액을 조회합니다."""
#           return balance_service.get(db, user_id)
#       return get_balance
#
# 방법 2 — tool 내부에서 직접 세션 생성:
#   @tool
#   def get_balance(user_id: str) -> str:
#       db = next(get_db())
#       try:
#           return balance_service.get(db, user_id)
#       finally:
#           db.close()


# ── tool 등록 체크리스트 ──────────────────────────────────────────────────────
#
# tool 작성 완료 후 아래를 확인하십시오:
#
# [ ] @tool 데코레이터 적용 완료
# [ ] docstring 첫 줄: 이 tool이 언제 호출되는지 명시
# [ ] docstring: 트리거 발화 예시 2~3개 포함
# [ ] Args: user_id 파라미터 포함
# [ ] Returns: TTS 친화 자연어 (마크다운 없음, 숫자 한국어)
# [ ] Raises: AppError 서브클래스만 사용
# [ ] tools/__init__.py 의 ALL_TOOLS 에 추가 완료
# [ ] pytest 테스트 작성 완료
