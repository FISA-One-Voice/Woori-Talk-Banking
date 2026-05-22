from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.account import Account


def get_user_accounts(db: Session, user_id: str) -> list[Account]:
    accounts = (
        db.query(Account)
        .filter(Account.user_id == user_id)
        .order_by(Account.created_at.asc())
        .all()
    )
    if not accounts:
        raise HTTPException(
            status_code=404,
            detail={"error": "ACCOUNT_NOT_FOUND"},
        )
    return accounts