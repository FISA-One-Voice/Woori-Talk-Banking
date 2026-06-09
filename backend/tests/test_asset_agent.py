# =============================================================================
# backend/tests/test_asset_agent.py
#
# [이 파일의 역할]
# AssetAgent 서브그래프 단독 테스트 (Supervisor 없이 격리 실행).
# 01-plan.md §6 "단독 테스트 계약" 기준으로 ASSET_READ 최소 필드만 주입한다.
#
# [실행 방법]
#   cd backend
#   pytest tests/test_asset_agent.py -v
#
# [전제 조건]
#   - .env에 OPENAI_CHAT_API_KEY, DATABASE_URL(또는 POSTGRES_*) 설정
#   - DB에 테스트 유저 및 계좌 데이터 존재 (seed_db.py 실행 후)
#     cd backend && python tests/seed_db.py
# =============================================================================

import pytest
from langchain_core.messages import HumanMessage

from app.shared.agent.subgraphs.asset import asset_graph

# seed_db.py로 생성된 테스트 유저 ID — 실제 DB에 존재해야 함
TEST_USER_ID = "b8bba706-5da6-4fb7-b3d4-a37a8487aed9"

# asset_graph.ainvoke에 필요한 LangGraph config
TEST_CONFIG = {"configurable": {"thread_id": "test-asset-agent"}}


def _make_state(utterance: str, period: str | None = None) -> dict:
    """ASSET_READ 기준 최소 필드만 가진 state를 반환한다."""
    return {
        "messages": [HumanMessage(content=utterance)],
        "user_id": TEST_USER_ID,
        "analytics_period": period,
        "agent_domain": "asset",
    }


# =============================================================================
# 1. 잔액 조회
# =============================================================================

class TestBalanceQuery:
    """패스트패스 경로: "잔액" 키워드 → LLM 없이 즉시 balance action."""

    @pytest.mark.asyncio
    async def test_balance_navigate_to(self):
        """잔액 발화 시 navigate_to가 'balance'인지 확인."""
        result = await asset_graph.ainvoke(_make_state("잔액 얼마야"), TEST_CONFIG)
        assert result.get("navigate_to") == "balance"

    @pytest.mark.asyncio
    async def test_balance_message_exists(self):
        """잔액 발화 시 AIMessage가 반환되는지 확인."""
        result = await asset_graph.ainvoke(_make_state("통장에 돈 얼마 있어"), TEST_CONFIG)
        messages = result.get("messages", [])
        assert len(messages) > 0

    @pytest.mark.asyncio
    async def test_balance_analytics_period_reset(self):
        """잔액 조회 후 analytics_period가 None으로 초기화되는지 확인."""
        result = await asset_graph.ainvoke(_make_state("잔액 얼마야"), TEST_CONFIG)
        assert result.get("analytics_period") is None

    @pytest.mark.asyncio
    async def test_balance_output_contract(self):
        """출력 계약: messages, navigate_to, analytics_period 필드만 반환하는지 확인."""
        result = await asset_graph.ainvoke(_make_state("전체 잔액 알려줘"), TEST_CONFIG)
        # Dev-C 출력 계약 외 필드가 있으면 안 됨
        forbidden_fields = {
            "pending_action", "collected_slots",
            "awaiting_confirmation", "awaiting_asv_audio",
        }
        for field in forbidden_fields:
            assert field not in result, f"출력 계약 위반: '{field}' 필드가 반환됨"


# =============================================================================
# 2. 거래내역 조회
# =============================================================================

class TestHistoryQuery:
    """history action: 거래내역 관련 발화 처리."""

    @pytest.mark.asyncio
    async def test_history_navigate_to(self):
        """거래내역 발화 시 navigate_to가 'balance'인지 확인."""
        result = await asset_graph.ainvoke(_make_state("이번달 거래내역 보여줘"), TEST_CONFIG)
        assert result.get("navigate_to") == "balance"

    @pytest.mark.asyncio
    async def test_history_message_exists(self):
        """거래내역 발화 시 AIMessage가 반환되는지 확인."""
        result = await asset_graph.ainvoke(_make_state("최근 내역 알려줘"), TEST_CONFIG)
        messages = result.get("messages", [])
        assert len(messages) > 0


# =============================================================================
# 3. 지출 분석
# =============================================================================

class TestSpendingAnalysis:
    """spending_analysis action: 분석/리포트 발화 → navigate_to='report'."""

    @pytest.mark.asyncio
    async def test_analysis_navigate_to(self):
        """지출 분석 발화 시 navigate_to가 'report'인지 확인."""
        result = await asset_graph.ainvoke(_make_state("이번달 지출 분석해줘"), TEST_CONFIG)
        assert result.get("navigate_to") == "report"

    @pytest.mark.asyncio
    async def test_analysis_period_set(self):
        """지출 분석 시 analytics_period가 설정되는지 확인."""
        result = await asset_graph.ainvoke(_make_state("지난달 소비 리포트 보여줘"), TEST_CONFIG)
        assert result.get("analytics_period") is not None

    @pytest.mark.asyncio
    async def test_analysis_message_exists(self):
        """지출 분석 발화 시 AIMessage가 반환되는지 확인."""
        result = await asset_graph.ainvoke(_make_state("소비 분석해줘"), TEST_CONFIG)
        messages = result.get("messages", [])
        assert len(messages) > 0


# =============================================================================
# 4. navigate_to 계약 검증
# =============================================================================

class TestNavigateToContract:
    """ASSET_NAVIGATE_VALUES 계약: 'balance', 'report', None 만 허용."""

    @pytest.mark.asyncio
    async def test_navigate_to_is_valid(self):
        """모든 발화에서 navigate_to가 허용값 안에 있는지 확인."""
        from app.shared.agent.ROUTING_CONSTANTS import ASSET_NAVIGATE_VALUES

        utterances = [
            "잔액 얼마야",
            "이번달 거래내역",
            "지출 분석해줘",
        ]
        for utt in utterances:
            result = await asset_graph.ainvoke(_make_state(utt), TEST_CONFIG)
            nav = result.get("navigate_to")
            assert nav in ASSET_NAVIGATE_VALUES, (
                f"navigate_to 계약 위반: '{utt}' 발화에서 '{nav}' 반환"
            )


# =============================================================================
# 5. analytics API 엔드포인트 테스트
# =============================================================================

class TestAnalyticsAPI:
    """GET /api/analytics/monthly 엔드포인트 테스트."""

    def test_monthly_requires_auth(self, client):
        """위조된 토큰이면 401 반환 확인."""
        response = client.get(
            "/api/analytics/monthly",
            headers={"Authorization": "Bearer invalid.token"},
        )
        assert response.status_code == 401

    def test_monthly_response_format(self, client):
        """인증 없이 요청 시 success 필드가 응답에 있는지 확인."""
        response = client.get("/api/analytics/monthly")
        data = response.json()
        assert "success" in data

    def test_monthly_period_param(self, client):
        """위조된 토큰으로 period 파라미터 요청 시 401 반환 확인."""
        response = client.get(
            "/api/analytics/monthly?period=지난달",
            headers={"Authorization": "Bearer invalid.token"},
        )
        assert response.status_code == 401
