"""이체 API 라우터."""

import base64

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.jwt_utils import get_current_user_id
from app.features.transfer import service
from app.features.transfer.schema import MemoUpdateRequest, TransferRequest
from app.shared.voice.tts_service import synthesize_speech

router = APIRouter(prefix="/api/transfer", tags=["Transfer"])


# GET /recent는 반드시 /{tx_id}/memo 보다 먼저 선언 — FastAPI는 선언 순서로 경로 매칭
@router.get("/recent", response_model=dict)
async def get_recent_recipients(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """최근 이체 완료 수취인 목록을 반환합니다 (최대 5건, 중복 제거).

    수취인이 있으면 DB 조회 1회로 목록과 TTS 오디오(base64)를 함께 반환한다.
    수취인이 없으면 tts_audio_base64를 null로 반환한다.
    """
    data = service.get_recent_recipients(db=db, user_id=user_id)

    if not data:
        return {
            "success": True,
            "data": {"recipients": [], "tts_audio_base64": None},
            "message": "최근 이체 내역이 없습니다.",
        }

    names = "님, ".join(r["toName"] for r in data) + "님"
    tts_text = f"최근 이체하신 분은 {names}입니다."
    audio_bytes = await synthesize_speech(tts_text)
    tts_audio_base64 = base64.b64encode(audio_bytes).decode()

    return {
        "success": True,
        "data": {"recipients": data, "tts_audio_base64": tts_audio_base64},
        "message": tts_text,
    }


@router.post("/", response_model=dict)
def create_transfer(
    req: TransferRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """이체를 실행합니다.

    idempotency_key 처리:
      - completed → 200 (기존 영수증 재반환, 재출금 없음)
      - failed   → 409 (key 소진, 새 key 발급 필요)
      - 없음     → 신규 이체 처리
    """
    data = service.execute_transfer(
        db=db,
        user_id=user_id,
        recipient=req.recipient,
        bank_name=req.bank_name,
        amount=req.amount,
        idempotency_key=req.idempotency_key,
        recipient_name=req.recipient_name,
        recipient_id=req.recipient_id,
    )
    return {"success": True, "data": data, "message": "이체가 완료되었습니다."}


@router.post("/{tx_id}/memo", response_model=dict)
def update_memo(
    tx_id: str,
    req: MemoUpdateRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """트랜잭션에 메모를 추가/수정합니다."""
    data = service.update_memo(db=db, user_id=user_id, tx_id=tx_id, memo=req.memo)
    return {"success": True, "data": data, "message": "메모가 업데이트되었습니다."}
