import uuid
from contextvars import ContextVar, Token

# asyncio task 단위로 격리되는 request_id 저장소.
# threading.local 대신 ContextVar를 사용해 async 환경에서 태스크 간 누수 방지.
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """현재 asyncio 태스크의 request_id를 반환합니다.

    Returns:
        설정된 request_id. 값이 없으면 새 UUID를 생성하여 반환합니다.
    """
    val = request_id_var.get()
    if not val:
        val = str(uuid.uuid4())
        request_id_var.set(val)
    return val


def set_request_id(request_id: str) -> Token:
    """request_id를 현재 컨텍스트에 설정합니다.

    Args:
        request_id: 설정할 request_id 문자열.

    Returns:
        reset() 호출에 필요한 Token 객체.
    """
    return request_id_var.set(request_id)
