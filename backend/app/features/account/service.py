# =============================================================================
# backend/app/features/account/service.py
#
# [이 파일의 역할]
# 계좌 관련 비즈니스 로직을 담당합니다.
# HTTP 요청/응답과 무관하게 순수 Python 함수로만 작성합니다.
#
# [다른 파일과의 관계]
# ├─ features/account/router.py → 이 파일의 함수를 호출합니다.
# └─ models/account.py          → Account ORM 모델을 사용합니다.
#
# [함수 목록]
# get_user_accounts → 특정 사용자의 계좌 목록 조회
# =============================================================================

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.account import Account


def get_user_accounts(db: Session, user_id: str) -> list[Account]:
    """
    특정 사용자의 계좌 목록을 조회합니다.

    Args:
        db: DB 세션 (router 에서 Depends(get_db) 로 주입)
        user_id: 조회할 사용자 UUID

    Returns:
        Account 객체 리스트 (생성일 오름차순 정렬)

    Raises:
        HTTPException(404): 계좌가 없을 때 ACCOUNT_NOT_FOUND
    """
    accounts = (
        db.query(Account)
        .filter(Account.user_id == user_id)  # WHERE user_id = '{user_id}'
        .order_by(Account.created_at.asc())  # ORDER BY created_at ASC
        .all()
    )

    if not accounts:
        raise HTTPException(
            status_code=404,
            detail={"error": "ACCOUNT_NOT_FOUND"},
        )

    return accounts