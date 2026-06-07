# Design Ref: §1.2 — 단방향 의존, graph·prompts만 노출
"""shared/agent 패키지.

외부에서 사용하는 공개 인터페이스:
    build_supervisor — 멀티에이전트 Supervisor 그래프 빌드 함수 (voice pipeline 진입점)
    build_graph      — 단일 에이전트 그래프 빌드 함수 (레거시 / 테스트용)
    SYSTEM_PROMPT    — 시각장애인 음성 뱅킹 시스템 프롬프트

Phase 2 tool 등록은 shared/agent/tools/__init__.py 참고.
"""

from app.shared.agent.graph import build_graph
from app.shared.agent.prompts import SYSTEM_PROMPT
from app.shared.agent.supervisor import build_supervisor

__all__ = ["build_graph", "build_supervisor", "SYSTEM_PROMPT"]
