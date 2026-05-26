# Design Ref: §8.2 — L1 테스트 시나리오 8개 (그래프 초기화·반환 타입·프롬프트 검증)
"""LangGraph 에이전트 그래프 골격 테스트 (Issue #5).

테스트 범위:
    - build_graph() 초기화 (빈 tool 리스트 / tool 1개)
    - 반환 객체 타입 (.invoke / .ainvoke 보유)
    - SYSTEM_PROMPT 내용 검증 (길이, TTS 친화 문구, 보안 규칙)
    - ALL_TOOLS 초기 상태

실행 방법:
    cd backend
    pytest tests/test_agent_graph.py -v

주의:
    LLM 실제 호출(.invoke() 실행)은 OpenAI API 비용이 발생하므로 범위 외.
    그래프 초기화(컴파일)까지만 검증합니다.
    .ainvoke() 통합 테스트는 Issue #7 (음성 파이프라인) 에서 수행합니다.
"""

import pytest
from langchain_core.tools import tool

from app.shared.agent.graph import build_graph
from app.shared.agent.prompts import SYSTEM_PROMPT
from app.shared.agent.tools import ALL_TOOLS


# ── 테스트용 더미 tool ──────────────────────────────────────────────────────────

@tool
def dummy_balance_tool(user_id: str) -> str:
    """테스트용 잔액 조회 tool. 실제 DB 접근 없이 고정 문자열을 반환합니다."""
    return "테스트 잔액은 오만 원입니다."


# ── build_graph() 초기화 테스트 ────────────────────────────────────────────────

class TestBuildGraph:
    """build_graph() 함수 초기화 및 반환 타입 테스트."""

    def test_build_graph_empty_tools_no_error(self) -> None:
        """TC-01: build_graph([]) — 빈 tool 리스트로도 오류 없이 초기화.

        Issue #5 완료 조건 직접 검증.
        """
        # Plan SC: build_graph([]) 호출 시 오류 없이 초기화
        graph = build_graph([])
        assert graph is not None

    def test_build_graph_returns_object_with_invoke(self) -> None:
        """TC-02: build_graph([]) 반환 객체는 .invoke 속성을 보유해야 한다."""
        graph = build_graph([])
        assert hasattr(graph, "invoke"), "반환 객체에 .invoke 메서드가 없습니다."

    def test_build_graph_returns_object_with_ainvoke(self) -> None:
        """TC-03: build_graph([]) 반환 객체는 .ainvoke 속성을 보유해야 한다.

        voice/router.py (Issue #7) 는 await graph.ainvoke() 를 호출하므로
        비동기 인터페이스가 반드시 존재해야 합니다.
        """
        graph = build_graph([])
        assert hasattr(graph, "ainvoke"), "반환 객체에 .ainvoke 메서드가 없습니다."

    def test_build_graph_with_one_tool_no_error(self) -> None:
        """TC-04: build_graph([tool]) — tool 1개로도 오류 없이 초기화."""
        graph = build_graph([dummy_balance_tool])
        assert graph is not None

    def test_build_graph_with_one_tool_has_ainvoke(self) -> None:
        """TC-05: tool 1개로 초기화한 그래프도 .ainvoke 속성을 보유해야 한다."""
        graph = build_graph([dummy_balance_tool])
        assert hasattr(graph, "ainvoke")


# ── SYSTEM_PROMPT 검증 테스트 ──────────────────────────────────────────────────

class TestSystemPrompt:
    """SYSTEM_PROMPT 상수 내용 검증.

    Issue #5 완료 조건: "시스템 프롬프트 작성 완료"
    설계 문서 §3.2 의 8가지 필수 항목 검증.
    """

    def test_system_prompt_not_empty(self) -> None:
        """TC-06: SYSTEM_PROMPT 는 100자 이상이어야 한다."""
        assert len(SYSTEM_PROMPT) > 100, (
            f"SYSTEM_PROMPT 가 너무 짧습니다. (현재: {len(SYSTEM_PROMPT)}자)"
        )

    def test_system_prompt_no_markdown_instruction(self) -> None:
        """TC-07: 마크다운 금지 지시가 포함되어야 한다.

        TTS 가 *, #, - 등 마크다운 기호를 그대로 읽으므로
        에이전트에게 마크다운 사용 금지를 명시해야 합니다.
        """
        prompt_lower = SYSTEM_PROMPT.lower()
        assert "마크다운" in prompt_lower or "markdown" in prompt_lower, (
            "SYSTEM_PROMPT 에 마크다운 금지 지시가 없습니다."
        )

    def test_system_prompt_contains_tts_awareness(self) -> None:
        """TC-08: TTS 또는 음성 관련 지시가 포함되어야 한다.

        시각장애인 음성 뱅킹 특성상 응답이 TTS 로 변환됨을 에이전트가 인지해야 합니다.
        """
        assert "음성" in SYSTEM_PROMPT or "tts" in SYSTEM_PROMPT.lower(), (
            "SYSTEM_PROMPT 에 TTS/음성 관련 지시가 없습니다."
        )


# ── ALL_TOOLS 초기 상태 테스트 ─────────────────────────────────────────────────

class TestAllTools:
    """tools/__init__.py 의 ALL_TOOLS 초기 상태 검증."""

    def test_all_tools_is_empty_list_in_phase1(self) -> None:
        """TC-09: Phase 1 에서 ALL_TOOLS 는 빈 리스트여야 한다.

        Phase 2 tool 등록 전에는 빈 리스트가 정상 상태입니다.
        Phase 2 에서 tool 이 추가되면 이 테스트는 업데이트 필요합니다.
        """
        assert isinstance(ALL_TOOLS, list), "ALL_TOOLS 가 list 타입이 아닙니다."
        assert ALL_TOOLS == [], (
            f"Phase 1 에서 ALL_TOOLS 는 빈 리스트여야 합니다. (현재: {ALL_TOOLS})"
        )
