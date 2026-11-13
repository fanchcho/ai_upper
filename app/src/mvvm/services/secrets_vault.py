"""密钥安全存储：操作系统钥匙串优先，不可用时退到「加密文件」。

对应 Deva `apps/desktop/src/main/services/secrets.ts` 的 `secrets:*` 五条通道。Deva 用 Electron
的 `safeStorage`（Windows DPAPI / macOS Keychain / Linux libsecret）加密后把 base64 密文写进
`~/.deva/secrets.json`。本工程有两个后端：

1. **keyring**（首选）：Python `keyring` 包 + 真实系统后端（GNOME Keyring / KWallet /
   macOS Keychain / Windows Credential Manager）。后端可用时，密钥只存在系统钥匙串里。
2. **加密文件**（回退）：没有可用钥匙串时（典型是本容器：`keyring.backends.fail.Keyring`），
   用 AES-256-GCM 加密后写 `DEVA_HOME/secrets.enc`，主密钥材料来自 `DEVA_HOME/.secrets.key`
   （首次生成，0600）。

**回退方案的安全边界必须说清楚**：`.secrets.key` 与 `secrets.enc` 在同一目录下，能读到密文的
本地用户通常也能读到密钥文件。这层加密防的是「密文被误拷进备份 / 日志 / issue」与「同机不同
用户的随手读取」，**不防**与本进程同权限的主动攻击者。没有系统钥匙串时这是已知代价，不是等价
替代；`describe_backend()` 把实际后端如实报给界面，由用户自己判断。

密钥明文绝不出服务层：对外只有 `has_secret`（布尔）；`get_secret` 仅供主进程内部组装请求头，
不映射成任何界面命令。

与 Deva 的差异：Deva 的 `secrets.json` 是 Electron `safeStorage` 的 base64 密文，Python 解不开
（DPAPI/Keychain 的密钥绑定 Electron 的应用身份），所以**不读旧密文**——用户在新工程重填一次。
"""
from __future__ import annotations

import base64
import json
import os
import secrets as _secrets
from pathlib import Path
from typing import Optional

from mvvm.services.secrets_crypto import AESGCM, derive_key

KEYRING_SERVICE = "deva"
SECRETS_FILE = "secrets.enc"
KEY_FILE = ".secrets.key"
BACKEND_ENV = "DEVA_SECRETS_BACKEND"  # keyring | file | auto（缺省）

_FILE_VERSION = 1
_KEY_BYTES = 32
_SALT_BYTES = 16
_NONCE_BYTES = 12


class SecretsDecryptError(RuntimeError):
    """密文解不开：主密钥被换 / 文件被篡改 / 文件不是本应用写的。不静默当作「没有密钥」。"""


def _keyring_module():
    """返回可用的 keyring 模块；未安装或后端是 fail.Keyring 时返回 None。"""
    try:
        import keyring
        from keyring.backends import fail
    except Exception:  # pragma: no cover - 未安装 keyring
        return None
    try:
        backend = keyring.get_keyring()
    except Exception:  # pragma: no cover - 后端初始化异常
        return None
    return None if isinstance(backend, fail.Keyring) else keyring


class SecretsVault:
    """密钥读写。纯 Python，不认识 Qt 与 ViewModel。"""

    def __init__(self, home: Optional[Path | str] = None, backend: Optional[str] = None) -> None:
        self._home = Path(home) if home is not None else _default_home()
        forced = (backend or os.environ.get(BACKEND_ENV, "auto")).strip().lower()
        self._forced = forced if forced in ("auto", "keyring", "file") else "auto"
        self._keyring = None
        self._backend: Optional[str] = None
        self._items: Optional[dict[str, str]] = None
        self._salt: Optional[bytes] = None
        self._master: Optional[bytes] = None

    # ── 后端判定 ──────────────────────────────────────────────────────────
    def describe_backend(self) -> str:
        """实际使用的后端：`keyring` / `file` / `none`。"""
        if self._backend is None:
            self._backend = self._pick_backend()
        return self._backend

    def _pick_backend(self) -> str:
        if self._forced in ("auto", "keyring"):
            self._keyring = _keyring_module()
            if self._keyring is not None:
                return "keyring"
            if self._forced == "keyring":
                return "none"
        return "file" if self._writable() else "none"

    def available(self) -> bool:
        """是否有可用的加密后端（对应 `secrets:available`）。"""
        return self.describe_backend() != "none"

    def _writable(self) -> bool:
        try:
            self._home.mkdir(parents=True, exist_ok=True)
            probe = self._home / ".write-probe"
            probe.write_text("", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return True
        except OSError:
            return False

    # ── 加密文件后端 ──────────────────────────────────────────────────────
    @property
    def _store_path(self) -> Path:
        return self._home / SECRETS_FILE

    @property
    def _key_path(self) -> Path:
        return self._home / KEY_FILE

    def _load_items(self) -> dict[str, str]:
        """读并解密条目表。文件不存在 → 空表；存在但解不开 → 抛 SecretsDecryptError。"""
        if self._items is not None:
            return self._items
        try:
            raw = self._store_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            self._items = {}
            return self._items
        except OSError as exc:
            raise SecretsDecryptError(f"读取密钥文件失败：{exc}") from exc
        try:
            payload = json.loads(raw)
            salt = base64.b64decode(str(payload["salt"]))
            nonce = base64.b64decode(str(payload["nonce"]))
            blob = base64.b64decode(str(payload["data"]))
            plaintext = AESGCM(derive_key(self._master_key(), salt)).decrypt(nonce, blob, None)
            parsed = json.loads(plaintext.decode("utf-8"))
            if not isinstance(parsed, dict):
                raise ValueError("条目表不是对象")
        except Exception as exc:  # noqa: BLE001 - 统一转成可读的解密失败
            raise SecretsDecryptError(
                f"密钥文件无法解密（主密钥 {self._key_path} 可能已被替换）：{exc}"
            ) from exc
        self._salt = salt
        self._items = {str(k): str(v) for k, v in parsed.items()}
        return self._items

    def _persist(self) -> None:
        """加密落盘。写失败抛 OSError —— 密钥没存上必须让调用方知道。"""
        items = self._load_items()
        salt = self._salt or _secrets.token_bytes(_SALT_BYTES)
        nonce = _secrets.token_bytes(_NONCE_BYTES)
        plaintext = json.dumps(items, ensure_ascii=False).encode("utf-8")
        blob = AESGCM(derive_key(self._master_key(), salt)).encrypt(nonce, plaintext, None)
        payload = {
            "v": _FILE_VERSION,
            "salt": base64.b64encode(salt).decode("ascii"),
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "data": base64.b64encode(blob).decode("ascii"),
        }
        self._home.mkdir(parents=True, exist_ok=True)
        tmp = self._store_path.with_name(self._store_path.name + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, json.dumps(payload, indent=2).encode("utf-8"))
        finally:
            os.close(fd)
        os.replace(tmp, self._store_path)
        self._salt = salt

    def _master_key(self) -> bytes:
        """主密钥材料：`DEVA_HOME/.secrets.key`，首次使用时生成（0600，O_EXCL 防并发覆盖）。"""
        if self._master is not None:
            return self._master
        try:
            raw = self._key_path.read_bytes()
            if len(raw) == _KEY_BYTES:
                self._master = raw
                return raw
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise SecretsDecryptError(f"读取主密钥失败：{exc}") from exc
        self._home.mkdir(parents=True, exist_ok=True)
        key = _secrets.token_bytes(_KEY_BYTES)
        try:
            fd = os.open(self._key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            # 并发首次使用：另一进程刚建好，读它写下的那一份（读不到/长度不对就明确报错）
            raw = self._key_path.read_bytes()
            if len(raw) != _KEY_BYTES:
                raise SecretsDecryptError(f"主密钥文件长度异常：{self._key_path}")
            self._master = raw
            return raw
        try:
            os.write(fd, key)
        finally:
            os.close(fd)
        self._master = key
        return key

    # ── 公共接口（与 Deva 的 secrets:* 一一对应）──────────────────────────
    def set_secret(self, key: str, value: str) -> dict[str, bool]:
        """写入 / 更新密钥；空串视为删除。后端不可用时返回 `{ok: False, available: False}`。"""
        backend = self.describe_backend()
        if not value:
            self.delete_secret(key)
            return {"ok": True, "available": backend != "none"}
        if backend == "none":
            return {"ok": False, "available": False}
        if backend == "keyring":
            assert self._keyring is not None
            self._keyring.set_password(KEYRING_SERVICE, key, value)
            self._remember_name(key)
            return {"ok": True, "available": True}
        self._load_items()[key] = value
        self._persist()
        self._remember_name(key)
        return {"ok": True, "available": True}

    def get_secret(self, key: str) -> Optional[str]:
        """主进程内部取明文（只给 provider 组装请求头用，不映射成界面命令）。"""
        backend = self.describe_backend()
        if backend == "keyring":
            assert self._keyring is not None
            try:
                return self._keyring.get_password(KEYRING_SERVICE, key)
            except Exception:  # pragma: no cover - 钥匙串被锁等
                return None
        if backend == "file":
            return self._load_items().get(key)
        return None

    def has_secret(self, key: str) -> bool:
        return bool(self.get_secret(key))

    def delete_secret(self, key: str) -> dict[str, bool]:
        backend = self.describe_backend()
        if backend == "keyring":
            assert self._keyring is not None
            try:
                self._keyring.delete_password(KEYRING_SERVICE, key)
            except Exception:
                pass  # 条目不存在时 keyring 抛 PasswordDeleteError；删除本身是幂等的
            self._forget_name(key)
            return {"ok": True, "available": True}
        if backend == "file":
            items = self._load_items()
            if key in items:
                del items[key]
                self._persist()
            self._forget_name(key)
        return {"ok": True, "available": backend != "none"}

    def list_keys(self) -> list[str]:
        """已配置密钥的键名（只有名字，没有值）。"""
        return sorted(self._load_names())

    # ── 键名清单（keyring 没有列条目的 API，用同名侧车记录名字）─────────────
    @property
    def _names_path(self) -> Path:
        return self._home / "secret-names.json"

    def _load_names(self) -> list[str]:
        try:
            parsed = json.loads(self._names_path.read_text(encoding="utf-8"))
            return [str(x) for x in parsed] if isinstance(parsed, list) else []
        except (OSError, ValueError, TypeError):
            return []

    def _write_names(self, names: list[str]) -> None:
        try:
            self._home.mkdir(parents=True, exist_ok=True)
            self._names_path.write_text(json.dumps(sorted(set(names)), ensure_ascii=False), "utf-8")
        except OSError:
            pass  # 名字清单只是界面提示；丢了不影响密钥本身

    def _remember_name(self, key: str) -> None:
        names = self._load_names()
        if key not in names:
            self._write_names(names + [key])

    def _forget_name(self, key: str) -> None:
        names = self._load_names()
        if key in names:
            self._write_names([n for n in names if n != key])


def _default_home() -> Path:
    override = os.environ.get("DEVA_HOME")
    return Path(override) if override else Path.home() / ".deva"


__all__ = [
    "BACKEND_ENV",
    "KEYRING_SERVICE",
    "SECRETS_FILE",
    "SecretsDecryptError",
    "SecretsVault",
]
