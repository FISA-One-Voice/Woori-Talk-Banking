"""AES-256-GCM 암호화/복호화 유틸리티.

암호화 대상 컬럼: resident_number, account_number (users·accounts·registered_recipients·transactions)
복호화는 반드시 이 모듈의 decrypt() 를 통해서만 수행한다.

no-op 모드(.env: CRYPTO_NOOP=true):
  encrypt/decrypt 가 평문을 그대로 반환한다.
  개발·테스트 환경 전용. 프로덕션에서 절대 사용 금지.

키 생성:
  python -c "import os, base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
  → 결과를 .env 의 CRYPTO_KEY 에 설정.
"""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

_NONCE_BYTES = 12  # AES-GCM 권장 nonce 크기 (96-bit)


def _key() -> bytes:
    """CRYPTO_KEY 환경변수에서 32바이트 키를 디코딩한다."""
    raw = settings.CRYPTO_KEY
    if not raw:
        raise RuntimeError(
            "CRYPTO_KEY 환경변수가 설정되지 않았습니다. "
            ".env 에 CRYPTO_KEY=<base64url_32bytes> 를 추가하세요."
        )
    decoded = base64.urlsafe_b64decode(raw.encode())
    if len(decoded) != 32:
        raise ValueError(
            f"CRYPTO_KEY 는 32바이트(256-bit)여야 합니다. 현재: {len(decoded)}바이트"
        )
    return decoded


def encrypt(plaintext: str | None) -> str | None:
    """plaintext 를 AES-256-GCM 으로 암호화한다.

    Args:
        plaintext: 암호화할 평문 문자열. None 이면 None 반환.

    Returns:
        base64url 인코딩된 암호문 (nonce 12바이트 포함).
        CRYPTO_NOOP=true 이면 plaintext 그대로 반환.

    Example::

        ciphertext = encrypt("951010-1234567")
        user.resident_number = ciphertext
    """
    if plaintext is None:
        return None
    if settings.CRYPTO_NOOP:
        return plaintext

    aesgcm = AESGCM(_key())
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode()


def decrypt(token: str | None) -> str | None:
    """AES-256-GCM 암호문을 복호화한다.

    Args:
        token: encrypt() 가 반환한 base64url 문자열. None 이면 None 반환.

    Returns:
        복호화된 평문 문자열.
        CRYPTO_NOOP=true 이면 token 그대로 반환.

    Raises:
        ValueError: 토큰 형식이 잘못되었거나 인증 태그 검증 실패 시.

    Example::

        raw = decrypt(user.resident_number)
        masked = raw[:6] + "-" + "*" * 7
    """
    if token is None:
        return None
    if settings.CRYPTO_NOOP:
        return token

    try:
        raw = base64.urlsafe_b64decode(token.encode())
    except Exception as e:
        raise ValueError(f"암호문 base64 디코딩 실패: {e}") from e

    if len(raw) <= _NONCE_BYTES:
        raise ValueError("암호문이 너무 짧습니다. 손상된 데이터일 수 있습니다.")

    nonce, ciphertext = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
    try:
        return AESGCM(_key()).decrypt(nonce, ciphertext, None).decode()
    except Exception as e:
        raise ValueError(f"복호화 실패 (키 불일치 또는 데이터 손상): {e}") from e
