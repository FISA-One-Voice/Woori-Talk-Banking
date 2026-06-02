# Design Ref: §1.2 — 단방향 의존, graph·prompts만 노출
"""shared/agent 패키지.

외부에서 사용하는 공개 인터페이스:
    build_graph  — LangGraph 그래프 빌드 함수
    SYSTEM_PROMPT — 시각장애인 음성 뱅킹 시스템 프롬프트

Phase 2 tool 등록은 shared/agent/tools/__init__.py 참고.
"""

from app.shared.agent.graph import build_graph
from app.shared.agent.prompts import SYSTEM_PROMPT

__all__ = ["build_graph", "SYSTEM_PROMPT"]
