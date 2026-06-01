"""이체 서비스 레이어 유닛 테스트.

검증 범위:
    - execute_transfer: 멱등성(completed/failed), 잔액 검증, 계좌번호 형식, recipient_id 경로
    - update_memo: 소유권 검증, 메모 업데이트
    - get_recent_recipients: recipient_id 기준 중복 제거, 최대 5건 제한

실행:
    cd backend
    CRYPTO_NOOP=true pytest tests/test_transfer_service.py -v
"""

import uuid

import pytest
from sqlalchemy.orm import Session

import app.models  # noqa: F401 — Base.metadata에 모든 테이블 등록
from app.core.exception import RecipientError, TransferError
from app.features.transfer.service import execute_transfer, get_recent_recipients, update_memo
from app.models.account import Account
from app.models.recipient import RegisteredRecipient
from app.models.transaction import Transaction
from app.models.user import User

# ── 고정 테스트 식별자 ──────────────────────────────────────────────────────────
# 다른 테스트 모듈과 충돌하지 않도록 고정 UUID 사용
_USER_UUID = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
_USER_ID = str(_USER_UUID)
_OTHER_UUID = uuid.UUID("d4e5f6a7-b8c9-0123-def0-234567890123")
_ACCOUNT_ID = "b2c3d4e5-f6a7-8901-bcde-f12345678901"
_RECIPIENT_ID = "c3d4e5f6-a7b8-9012-cdef-123456789012"
_INITIAL_BALANCE = 5_000_000


# ── 공통 픽스처 ────────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def patch_for_update(monkeypatch):
    """SQLite 호환을 위해 SELECT FOR UPDATE를 no-op으로 패치.
    PostgreSQL에서는 실제 행 락이 걸리지만, 테스트 환경에서는 로직 검증이 목적이므로 생략.
    """
    from sqlalchemy.orm import Query

    monkeypatch.setattr(Query, "with_for_update", lambda self, **kw: self)


@pytest.fixture(scope="module")
def transfer_setup(db: Session):
    """모듈 공유 테스트 데이터 생성 + 모듈 종료 시 정리.

    생성:
        - 테스트 사용자 (_USER_UUID): 주계좌 잔액 5,000,000원
        - 타인 사용자 (_OTHER_UUID): 메모 소유권 테스트용
        - 등록 수취인 (_RECIPIENT_ID): recipient_id 경로 테스트용

    사전 정리: 이전 실행에서 teardown이 실패한 경우 잔류 데이터를 제거한다.
    """
    # 이전 실행 잔류 데이터 정리 (teardown 실패 등으로 남은 데이터)
    db.query(Transaction).filter(Transaction.user_id.in_([_USER_UUID, _OTHER_UUID])).delete()
    db.query(RegisteredRecipient).filter(RegisteredRecipient.user_id == _USER_UUID).delete()
    db.query(Account).filter(Account.user_id.in_([_USER_UUID, _OTHER_UUID])).delete()
    db.query(User).filter(User.user_id.in_([_USER_UUID, _OTHER_UUID])).delete()
    db.commit()

    user = User(user_id=_USER_UUID, name="이체서비스테스터", phone="01077771001", pin_hash="x")
    other = User(user_id=_OTHER_UUID, name="타인", phone="01077771002", pin_hash="x")
    account = Account(
        account_id=_ACCOUNT_ID,
        user_id=_USER_UUID,
        bank_name="우리은행",
        account_number="12345678901234",
        account_type="입출금",
        balance=_INITIAL_BALANCE,
        is_primary=True,
    )
    recipient = RegisteredRecipient(
        recipient_id=_RECIPIENT_ID,
        user_id=_USER_UUID,
        alias="엄마",
        bank_name="국민은행",
        account_number="98765432101234",
        recipient_name="홍길순",
    )
    db.add_all([user, other, account, recipient])
    db.commit()

    yield

    # 모듈 종료 시 테스트 데이터 전체 삭제
    db.query(Transaction).filter(Transaction.user_id.in_([_USER_UUID, _OTHER_UUID])).delete()
    db.query(RegisteredRecipient).filter(RegisteredRecipient.user_id == _USER_UUID).delete()
    db.query(Account).filter(Account.user_id.in_([_USER_UUID, _OTHER_UUID])).delete()
    db.query(User).filter(User.user_id.in_([_USER_UUID, _OTHER_UUID])).delete()
    db.commit()


# ── TestExecuteTransfer ────────────────────────────────────────────────────────
class TestExecuteTransfer:
    def test_success(self, db: Session, transfer_setup):
        """[정상 이체] 유효한 계좌번호와 충분한 잔액으로 이체 시
        → status=completed, 잔액이 amount만큼 차감되어야 한다."""
        account = db.query(Account).filter(Account.account_id == _ACCOUNT_ID).first()
        balance_before = account.balance
        key = str(uuid.uuid4())

        result = execute_transfer(
            db=db,
            user_id=_USER_ID,
            recipient="12345678901",
            bank_name="하나은행",
            amount=10_000,
            idempotency_key=key,
            recipient_name="홍길동",
            recipient_id=None,
        )

        db.refresh(account)
        assert result["status"] == "completed"
        assert account.balance == balance_before - 10_000

        # 테스트 데이터 정리
        db.query(Transaction).filter(Transaction.idempotency_key == key).delete()
        db.commit()

    def test_insufficient_balance(self, db: Session, transfer_setup):
        """[잔액 부족] 이체 금액이 잔액을 초과하면
        → TransferError(INSUFFICIENT_BALANCE, 400)이 발생하고
        → tx.status='failed'로 커밋되어 해당 idempotency_key가 소진되어야 한다."""
        # 잔액을 강제로 50원으로 설정
        account = db.query(Account).filter(Account.account_id == _ACCOUNT_ID).first()
        account.balance = 50
        db.commit()

        key = str(uuid.uuid4())
        with pytest.raises(TransferError) as exc_info:
            execute_transfer(
                db=db,
                user_id=_USER_ID,
                recipient="12345678901",
                bank_name="하나은행",
                amount=1_000,  # 잔액(50) < 이체금액(1,000)
                idempotency_key=key,
                recipient_name=None,
                recipient_id=None,
            )

        assert exc_info.value.code == "INSUFFICIENT_BALANCE"
        assert exc_info.value.status_code == 400

        # 실패 트랜잭션이 DB에 남아있어야 함 (idempotency_key 소진 확인)
        failed_tx = db.query(Transaction).filter(Transaction.idempotency_key == key).first()
        assert failed_tx is not None
        assert failed_tx.status == "failed"

        # 잔액 복구 + 실패 TX 정리
        account = db.query(Account).filter(Account.account_id == _ACCOUNT_ID).first()
        account.balance = _INITIAL_BALANCE
        db.query(Transaction).filter(Transaction.idempotency_key == key).delete()
        db.commit()

    def test_invalid_account_format(self, db: Session, transfer_setup):
        """[계좌번호 형식 오류] 숫자가 아닌 문자열 또는 길이 미달 계좌번호 입력 시
        → TransferError(INVALID_ACCOUNT_FORMAT, 400)이 발생해야 한다."""
        with pytest.raises(TransferError) as exc_info:
            execute_transfer(
                db=db,
                user_id=_USER_ID,
                recipient="abc",  # 유효하지 않은 형식
                bank_name="하나은행",
                amount=1_000,
                idempotency_key=str(uuid.uuid4()),
                recipient_name=None,
                recipient_id=None,
            )

        assert exc_info.value.code == "INVALID_ACCOUNT_FORMAT"
        assert exc_info.value.status_code == 400

    def test_idempotency_completed(self, db: Session, transfer_setup):
        """[멱등성 - completed] 이미 완료된 트랜잭션의 idempotency_key로 재요청 시
        → 기존 영수증을 그대로 반환하고, 잔액 차감은 일어나지 않아야 한다 (중복 출금 방지)."""
        key = str(uuid.uuid4())
        completed_tx = Transaction(
            user_id=_USER_UUID,
            from_account_id=_ACCOUNT_ID,
            to_bank_name="하나은행",
            to_name="홍길동",
            amount=5_000,
            tx_type="transfer",
            status="completed",
            idempotency_key=key,
        )
        db.add(completed_tx)
        db.commit()

        account = db.query(Account).filter(Account.account_id == _ACCOUNT_ID).first()
        balance_before = account.balance

        result = execute_transfer(
            db=db,
            user_id=_USER_ID,
            recipient="12345678901",
            bank_name="하나은행",
            amount=5_000,
            idempotency_key=key,  # 이미 completed 상태의 key 재사용
            recipient_name="홍길동",
            recipient_id=None,
        )

        db.refresh(account)
        # 동일한 txId 반환 (새 트랜잭션 생성 없음)
        assert result["txId"] == completed_tx.tx_id
        assert result["status"] == "completed"
        # 잔액 변동 없음 (재출금 없음)
        assert account.balance == balance_before

        db.query(Transaction).filter(Transaction.idempotency_key == key).delete()
        db.commit()

    def test_idempotency_failed(self, db: Session, transfer_setup):
        """[멱등성 - failed] 이전에 실패(잔액 부족 등)한 트랜잭션의 key로 재시도 시
        → TransferError(IDEMPOTENCY_KEY_USED, 409)이 발생해야 한다.
        클라이언트는 새 idempotency_key를 발급해서 재시도해야 함."""
        key = str(uuid.uuid4())
        failed_tx = Transaction(
            user_id=_USER_UUID,
            from_account_id=_ACCOUNT_ID,
            to_bank_name="하나은행",
            amount=1_000,
            tx_type="transfer",
            status="failed",
            idempotency_key=key,
        )
        db.add(failed_tx)
        db.commit()

        with pytest.raises(TransferError) as exc_info:
            execute_transfer(
                db=db,
                user_id=_USER_ID,
                recipient="12345678901",
                bank_name="하나은행",
                amount=1_000,
                idempotency_key=key,  # 이미 소진된 key
                recipient_name=None,
                recipient_id=None,
            )

        assert exc_info.value.code == "IDEMPOTENCY_KEY_USED"
        assert exc_info.value.status_code == 409

        db.query(Transaction).filter(Transaction.idempotency_key == key).delete()
        db.commit()

    def test_with_recipient_id(self, db: Session, transfer_setup):
        """[등록 수취인 경로] recipient_id를 제공하면 registered_recipients 테이블에서
        은행명/계좌번호/수취인명을 자동으로 가져와야 한다."""
        account = db.query(Account).filter(Account.account_id == _ACCOUNT_ID).first()
        balance_before = account.balance
        key = str(uuid.uuid4())

        result = execute_transfer(
            db=db,
            user_id=_USER_ID,
            recipient="",   # recipient_id가 있으면 이 값은 무시됨
            bank_name="",
            amount=2_000,
            idempotency_key=key,
            recipient_name=None,
            recipient_id=_RECIPIENT_ID,  # 등록된 수취인 "엄마"
        )

        db.refresh(account)
        assert result["status"] == "completed"
        # 등록 수취인의 은행명/이름이 자동으로 채워져야 함
        assert result["toBankName"] == "국민은행"
        assert result["toName"] == "홍길순"
        assert account.balance == balance_before - 2_000

        db.query(Transaction).filter(Transaction.idempotency_key == key).delete()
        db.commit()

    def test_invalid_recipient_id(self, db: Session, transfer_setup):
        """[잘못된 recipient_id] DB에 존재하지 않는 recipient_id 입력 시
        → RecipientError(404)가 발생해야 한다."""
        with pytest.raises(RecipientError) as exc_info:
            execute_transfer(
                db=db,
                user_id=_USER_ID,
                recipient="",
                bank_name="",
                amount=1_000,
                idempotency_key=str(uuid.uuid4()),
                recipient_name=None,
                recipient_id="00000000-0000-0000-0000-000000000000",  # 존재하지 않는 ID
            )

        assert exc_info.value.status_code == 404


# ── TestUpdateMemo ─────────────────────────────────────────────────────────────
class TestUpdateMemo:
    def test_success(self, db: Session, transfer_setup):
        """[메모 업데이트 성공] 본인 소유 트랜잭션의 memo 필드가 정상적으로 갱신되어야 한다."""
        tx = Transaction(
            user_id=_USER_UUID,
            from_account_id=_ACCOUNT_ID,
            to_bank_name="하나은행",
            amount=1_000,
            tx_type="transfer",
            status="completed",
        )
        db.add(tx)
        db.commit()

        result = update_memo(db=db, user_id=_USER_ID, tx_id=tx.tx_id, memo="용돈")

        db.refresh(tx)
        assert result["memo"] == "용돈"
        assert tx.memo == "용돈"  # DB에도 반영되었는지 확인

        db.delete(tx)
        db.commit()

    def test_not_owner(self, db: Session, transfer_setup):
        """[소유권 검증] 타인의 트랜잭션에 메모를 업데이트하려 하면
        → TransferError(TRANSACTION_NOT_FOUND, 404)가 발생해야 한다."""
        tx = Transaction(
            user_id=_USER_UUID,  # _USER_UUID 소유
            from_account_id=_ACCOUNT_ID,
            to_bank_name="하나은행",
            amount=1_000,
            tx_type="transfer",
            status="completed",
        )
        db.add(tx)
        db.commit()

        with pytest.raises(TransferError) as exc_info:
            # _OTHER_UUID가 _USER_UUID 소유의 트랜잭션에 접근 시도
            update_memo(db=db, user_id=str(_OTHER_UUID), tx_id=tx.tx_id, memo="훔치기")

        assert exc_info.value.code == "TRANSACTION_NOT_FOUND"
        assert exc_info.value.status_code == 404

        db.delete(tx)
        db.commit()


# ── TestGetRecentRecipients ────────────────────────────────────────────────────
class TestGetRecentRecipients:
    def test_dedup_by_recipient_id(self, db: Session, transfer_setup):
        """[중복 제거] 동일 recipient_id로 3번 이체해도 결과에 1건만 반환되어야 한다.
        AES-256-GCM 비결정적 암호화로 to_account_number GROUP BY 불가하므로
        recipient_id 기준으로 중복을 제거한다."""
        # 같은 수취인에게 3번 이체
        txs = [
            Transaction(
                user_id=_USER_UUID,
                from_account_id=_ACCOUNT_ID,
                recipient_id=_RECIPIENT_ID,
                to_bank_name="국민은행",
                to_account_number="98765432101234",
                to_name="홍길순",
                amount=1_000,
                tx_type="transfer",
                status="completed",
            )
            for _ in range(3)
        ]
        db.add_all(txs)
        db.commit()

        result = get_recent_recipients(db=db, user_id=_USER_ID)
        # 동일 recipient_id는 1건으로 중복 제거되어야 함
        matching = [r for r in result if r["recipientId"] == _RECIPIENT_ID]
        assert len(matching) == 1

        for tx in txs:
            db.delete(tx)
        db.commit()

    def test_max_5(self, db: Session, transfer_setup):
        """[최대 5건 제한] 6개의 서로 다른 수취인에게 이체해도 최대 5건만 반환되어야 한다."""
        extra_recipients = []
        extra_txs = []
        for i in range(6):
            r_id = str(uuid.uuid4())
            r = RegisteredRecipient(
                recipient_id=r_id,
                user_id=_USER_UUID,
                alias=f"최근테스트{i}",
                bank_name="국민은행",
                account_number=f"9876543210{i:04d}",
                recipient_name=f"홍길동{i}",
            )
            t = Transaction(
                user_id=_USER_UUID,
                from_account_id=_ACCOUNT_ID,
                recipient_id=r_id,
                to_bank_name="국민은행",
                to_account_number=f"9876543210{i:04d}",
                to_name=f"홍길동{i}",
                amount=1_000,
                tx_type="transfer",
                status="completed",
            )
            extra_recipients.append(r)
            extra_txs.append(t)

        db.add_all(extra_recipients)
        db.flush()
        db.add_all(extra_txs)
        db.commit()

        result = get_recent_recipients(db=db, user_id=_USER_ID)
        # LIMIT 5이므로 6건 중 최대 5건만 반환
        assert len(result) <= 5

        for tx in extra_txs:
            db.delete(tx)
        for r in extra_recipients:
            db.delete(r)
        db.commit()
