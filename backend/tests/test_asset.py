# =============================================================================
# backend/tests/test_asset.py
#
# [이 파일의 역할]
# 자산 화면 API pytest 테스트 코드.
# 실행: cd backend && pytest tests/ -v
# =============================================================================

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestAssetSummary:
    """GET /api/asset/summary 테스트"""

    def test_summary_requires_auth(self):
        """위조된 토큰이면 401 반환 확인."""
        response = client.get(
            "/api/asset/summary", headers={"Authorization": "Bearer invalid.token"}
        )
        assert response.status_code == 401

    def test_summary_response_format(self):
        """응답 형식이 표준 ApiResponse 형태인지 확인."""
        response = client.get("/api/asset/summary")
        data = response.json()
        assert "success" in data


class TestAccountBalance:
    """GET /api/asset/balance/{account_id} 테스트"""

    def test_balance_requires_auth(self):
        """위조된 토큰이면 401 반환 확인."""
        response = client.get(
            "/api/asset/balance/test-id",
            headers={"Authorization": "Bearer invalid.token"},
        )
        assert response.status_code == 401

    def test_balance_not_found(self):
        """위조된 토큰으로 존재하지 않는 계좌 조회 시 401 반환 확인."""
        response = client.get(
            "/api/asset/balance/non-existent-id",
            headers={"Authorization": "Bearer invalid.token"},
        )
        assert response.status_code == 401


class TestTransactionHistory:
    """GET /api/asset/history 테스트"""

    def test_history_requires_auth(self):
        """위조된 토큰이면 401 반환 확인."""
        response = client.get(
            "/api/asset/history", headers={"Authorization": "Bearer invalid.token"}
        )
        assert response.status_code == 401

    def test_history_with_days_filter(self):
        """위조된 토큰으로 days 필터 요청 시 401 반환 확인."""
        response = client.get(
            "/api/asset/history?days=7",
            headers={"Authorization": "Bearer invalid.token"},
        )
        assert response.status_code == 401

    def test_history_with_category_filter(self):
        """위조된 토큰으로 category 필터 요청 시 401 반환 확인."""
        response = client.get(
            "/api/asset/history?category=식비",
            headers={"Authorization": "Bearer invalid.token"},
        )
        assert response.status_code == 401

    def test_history_response_format(self):
        """응답 형식 확인."""
        response = client.get("/api/asset/history")
        data = response.json()
        assert "success" in data


class TestExpenseSummary:
    """GET /api/asset/expense-summary 테스트"""

    def test_expense_summary_requires_auth(self):
        """위조된 토큰이면 401 반환 확인."""
        response = client.get(
            "/api/asset/expense-summary",
            headers={"Authorization": "Bearer invalid.token"},
        )
        assert response.status_code == 401

    def test_expense_summary_with_days_param(self):
        """위조된 토큰으로 days 파라미터 요청 시 401 반환 확인."""
        response = client.get(
            "/api/asset/expense-summary?days=7",
            headers={"Authorization": "Bearer invalid.token"},
        )
        assert response.status_code == 401

    def test_expense_summary_response_format(self):
        """응답 형식이 표준 ApiResponse 형태인지 확인."""
        response = client.get("/api/asset/expense-summary")
        data = response.json()
        assert "success" in data
