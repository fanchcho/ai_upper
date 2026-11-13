"""加密原语：AES-256-GCM 与口令派生。

为什么用 `cryptography` 而不是自己写：对称加密的实现细节（GCM 的计数器、认证标签、
侧信道）不是能靠标准库 `hashlib` / `hmac` 拼出来的东西，自己实现就是把密钥安全押在
未经验证的代码上。`cryptography` 是 CPython 生态里这类需求的既成标准，wheel 里带
OpenSSL，不需要系统头文件。

这一层刻意做得很薄：只暴露 `derive_key` 与再导出的 `AESGCM`，方便测试替换与审计。
"""
from __future__ import annotations

from typing import Optional

try:  # pragma: no cover - 导入失败时由调用方给出可读错误
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except Exception as exc:  # pragma: no cover
    raise ImportError(
        "密钥加密需要 cryptography 包（pip install -r app/requirements.txt）："
        f"{exc}"
    ) from exc

_SALT_INFO = b"deva-secrets-v1"


def derive_key(master: bytes, salt: bytes, *, length: int = 32) -> bytes:
    """把 32 字节主密钥材料与盐派生成 AES-256 密钥（HKDF-SHA256）。

    主密钥本身已是随机 32 字节，这里用 HKDF 而不是 scrypt/PBKDF2 是有意的：
    PBKDF2 的迭代是为了拖慢**人类口令**的暴力猜测，而输入不是口令、是等长随机串，
    加迭代只会让每次启动多花时间而不增加任何安全性。
    """
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    hkdf = HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=_SALT_INFO)
    return hkdf.derive(master)


def encrypt(master: bytes, salt: bytes, plaintext: bytes, nonce: Optional[bytes] = None) -> tuple[bytes, bytes]:
    """加密并为每次调用生成新 nonce（GCM 的 nonce 绝不可复用）。返回 (nonce, 密文)。"""
    import os

    n = nonce or os.urandom(12)
    return n, AESGCM(derive_key(master, salt)).encrypt(n, plaintext, None)


def decrypt(master: bytes, salt: bytes, nonce: bytes, blob: bytes) -> bytes:
    """解密；密文被篡改或密钥不对时抛 `cryptography.exceptions.InvalidTag`。"""
    return AESGCM(derive_key(master, salt)).decrypt(nonce, blob, None)


__all__ = ["AESGCM", "decrypt", "derive_key", "encrypt"]
