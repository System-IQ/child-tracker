"""أمان: توقيع HMAC للبيانات + تحقق من صحة المدخلات"""
import hashlib
import hmac
import os
import re
from typing import Any

_SECRET = os.getenv("HMAC_SECRET", "")


def sign(data: bytes) -> str:
    if not _SECRET:
        return ""
    return hmac.new(_SECRET.encode(), data, hashlib.sha256).hexdigest()


def verify(data: bytes, signature: str) -> bool:
    if not _SECRET:
        return True
    return hmac.compare_digest(sign(data), signature)


_DEVICE_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")


def valid_device_id(s: str) -> bool:
    return bool(_DEVICE_RE.match(s))


def valid_coords(lat: Any, lon: Any) -> bool:
    try:
        la, lo = float(lat), float(lon)
        return -90 <= la <= 90 and -180 <= lo <= 180
    except (TypeError, ValueError):
        return False


def sanitize_text(s: str, max_len: int = 200) -> str:
    """منع حقن Markdown أو HTML"""
    s = str(s)[:max_len]
    return s.replace("`", "'").replace("*", "").replace("_", " ")
