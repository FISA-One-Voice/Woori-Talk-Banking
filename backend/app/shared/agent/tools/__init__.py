"""에이전트 tool 등록 포인트.

Phase 1 상태: ALL_TOOLS = [] (빈 리스트)
Phase 2에서 각 화면 담당자가 아래 패턴으로 tool을 추가합니다.

    등록 방법 (tool 작성 가이드는 _sample.py 참고):

    from app.shared.agent.tools.balance import get_balance, get_accounts
    from app.shared.agent.tools.transfer import execute_transfer
    ALL_TOOLS = [get_balance, get_accounts, execute_transfer, ...]

주의:
    - _sample.py 는 가이드 파일이므로 여기에 import 하지 마십시오.
    - tool 파일명은 features/ 화면명과 동일하게 유지하십시오.
      예: features/balance/ → tools/balance.py
"""

from app.shared.agent.tools.auth import check_auth_status, agent_logout

# Plan SC: build_graph([]) 호출 시 오류 없이 초기화 (Issue #5 완료 조건)
ALL_TOOLS: list = [check_auth_status, agent_logout]

__all__ = ["ALL_TOOLS"]
