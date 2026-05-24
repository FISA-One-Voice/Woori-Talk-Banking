# main.py의 Base.metadata.create_all()이 모든 테이블을 인식하려면
# 이 파일에서 모든 모델을 import해야 합니다.
from app.models.user import User
from app.models.account import Account
from app.models.recipient import RegisteredRecipient
from app.models.transaction import Transaction
from app.models.standing_order import StandingOrder
from app.models.event import Event, EventParticipation

__all__ = [
    "User",
    "Account",
    "RegisteredRecipient",
    "Transaction",
    "StandingOrder",
    "Event",
    "EventParticipation",
]
