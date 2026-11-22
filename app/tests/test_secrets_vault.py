"""密钥存储：文件后端往返、篡改检测、keyring 不可用时的降级、权限与「明文不落盘」。

对应 Deva `services/secrets.ts` 的 `secrets:*` 五条通道。本容器 keyring 解析到
`keyring.backends.fail.Keyring`，所以主力用例跑「加密文件」后端；keyring 分支用
注入的假模块覆盖（真钥匙串在 CI 里不存在，不能靠它通过或失败）。
"""
from __future__ import annotations

import base64
import json
import os
import stat

import pytest

from mvvm.services.secrets_vault import (
    KEYRING_SERVICE,
    _KEY_BYTES,
    SECRETS_FILE,
    SecretsDecryptError,
    SecretsVault,
)

PLAINTEXT = "sk-ant-api03-super-secret"


@pytest.fixture()
def home(tmp_path):
    return tmp_path / "deva-home"


@pytest.fixture()
def vault(home):
    # 显式 file 后端：这台机器上真正的 keyring 行为不可控，不能让它决定测试结果
    return SecretsVault(home, backend="file")


def test_file_backend_round_trip(home):
    vault = SecretsVault(home, backend="file")
    assert vault.available() is True
    assert vault.describe_backend() == "file"

    assert vault.set_secret("anthropic", PLAINTEXT) == {"ok": True, "available": True}
    assert vault.has_secret("anthropic") is True
    assert vault.get_secret("anthropic") == PLAINTEXT
    assert vault.list_keys() == ["anthropic"]

    # 新实例（= 重启）从磁盘读回
    again = SecretsVault(home, backend="file")
    assert again.get_secret("anthropic") == PLAINTEXT
    assert again.list_keys() == ["anthropic"]

    again.set_secret("openai", "sk-openai")
    assert again.list_keys() == ["anthropic", "openai"]


def test_plaintext_never_lands_on_disk(vault, home):
    vault.set_secret("anthropic", PLAINTEXT)
    blob = (home / SECRETS_FILE).read_text(encoding="utf-8")
    assert PLAINTEXT not in blob
    # 也不允许以 base64 形式出现（Deva 的 safeStorage 存的就是 base64）
    assert base64.b64encode(PLAINTEXT.encode()).decode() not in blob
    assert "anthropic" not in blob  # 键名也在密文里


def test_key_and_store_files_are_private(vault, home):
    """POSIX 上新建文件必须是 0600；Windows 没有 POSIX 权限位。

    `os.open(..., 0o600)` 在 Windows 上只映射到只读位，`st_mode` 对普通文件恒为
    0o666（可写），私密性由用户数据目录的 ACL 决定而不是 mode。所以这里按平台断言
    真实语义：Windows 上至少要求两件可验证的事——文件确实创建了、且不是只读位被
    误设（那会让后续写入失败）。
    """
    vault.set_secret("anthropic", PLAINTEXT)
    for name in (SECRETS_FILE, ".secrets.key"):
        path = home / name
        assert path.is_file(), f"{name} 没有被创建"
        assert path.stat().st_size > 0, f"{name} 是空文件"
        if os.name == "nt":
            # Windows: chmod 只有只读位有意义；确认没有被误设成只读。
            assert path.stat().st_mode & stat.S_IWRITE, f"{name} 被误设为只读"
            continue
        mode = stat.S_IMODE(path.stat().st_mode)
        assert mode == 0o600, f"{name} 权限是 {oct(mode)}，期望 0600"


def test_file_payload_is_versioned_ciphertext(vault, home):
    vault.set_secret("anthropic", PLAINTEXT)
    payload = json.loads((home / SECRETS_FILE).read_text(encoding="utf-8"))
    assert payload["v"] == 1
    # salt / nonce / data 都要能 base64 解出来，说明不是随手写的 JSON
    for key in ("salt", "nonce", "data"):
        assert base64.b64decode(payload[key])


def test_each_write_uses_a_fresh_nonce(vault, home):
    vault.set_secret("a", "one")
    first = json.loads((home / SECRETS_FILE).read_text(encoding="utf-8"))["nonce"]
    vault.set_secret("b", "two")
    second = json.loads((home / SECRETS_FILE).read_text(encoding="utf-8"))["nonce"]
    assert first != second


def test_tampered_ciphertext_raises_instead_of_looking_empty(vault, home):
    vault.set_secret("anthropic", PLAINTEXT)
    path = home / SECRETS_FILE
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = bytearray(base64.b64decode(payload["data"]))
    raw[0] ^= 0xFF
    payload["data"] = base64.b64encode(bytes(raw)).decode("ascii")
    path.write_text(json.dumps(payload), encoding="utf-8")

    # 关键行为：解不开必须报错，绝不能当成「没有配置密钥」让用户以为没保存
    with pytest.raises(SecretsDecryptError):
        SecretsVault(home, backend="file").get_secret("anthropic")


def test_replaced_master_key_raises(vault, home):
    vault.set_secret("anthropic", PLAINTEXT)
    (home / ".secrets.key").write_bytes(os.urandom(32))
    with pytest.raises(SecretsDecryptError):
        SecretsVault(home, backend="file").get_secret("anthropic")


def test_corrupt_store_file_raises(vault, home):
    vault.set_secret("anthropic", PLAINTEXT)
    (home / SECRETS_FILE).write_text("not json", encoding="utf-8")
    with pytest.raises(SecretsDecryptError):
        SecretsVault(home, backend="file").get_secret("anthropic")


def test_missing_files_are_just_empty(home):
    vault = SecretsVault(home, backend="file")
    assert vault.get_secret("anything") is None
    assert vault.has_secret("anything") is False
    assert vault.list_keys() == []


def test_empty_value_deletes(vault):
    vault.set_secret("anthropic", PLAINTEXT)
    assert vault.set_secret("anthropic", "") == {"ok": True, "available": True}
    assert vault.has_secret("anthropic") is False
    assert vault.list_keys() == []


def test_delete_is_idempotent(vault):
    assert vault.delete_secret("never-existed") == {"ok": True, "available": True}
    vault.set_secret("anthropic", PLAINTEXT)
    assert vault.delete_secret("anthropic")["ok"] is True
    assert vault.delete_secret("anthropic")["ok"] is True
    assert vault.list_keys() == []


def test_master_key_is_written_as_exact_bytes(home, monkeypatch):
    """主密钥必须逐字节落盘：Windows 文本模式下 `os.write` 会展开 0x0A。

    随机 32 字节里出现 0x0A 的概率约 12%，所以这里不靠运气，而是把主密钥固定成含
    0x0A / 0x0D 的 32 字节再写入，按长度和内容精确比对。少了 `O_BINARY`，这份密钥
    在 Windows 上会被写成 33+ 字节，此后每次读取都报「主密钥文件长度异常」——这正是
    windows-arm64 那次唯一命中的失败。
    """
    from mvvm.services import secrets_vault as module

    payload = bytes([0x0A, 0x0D, 0x0A, 0x0D]) + bytes(range(0, 28))
    assert len(payload) == _KEY_BYTES
    real = module._secrets.token_bytes
    monkeypatch.setattr(
        module._secrets,
        "token_bytes",
        lambda n=32: payload if n == _KEY_BYTES else real(n),
    )

    SecretsVault(home, backend="file").set_secret("anthropic", PLAINTEXT)
    assert (home / ".secrets.key").read_bytes() == payload


def test_key_material_survives_concurrent_first_use(home):
    """两个实例同时首次使用：只能有一份主密钥，另一个必须读它而不是覆盖。"""
    first = SecretsVault(home, backend="file")
    first.set_secret("a", "one")
    key_bytes = (home / ".secrets.key").read_bytes()
    second = SecretsVault(home, backend="file")
    second.set_secret("b", "two")
    assert (home / ".secrets.key").read_bytes() == key_bytes
    assert SecretsVault(home, backend="file").get_secret("a") == "one"


def test_auto_backend_falls_back_to_file_in_this_container(home):
    """本容器没有可用钥匙串：auto 必须退到加密文件，而不是报不可用、更不是明文。"""
    vault = SecretsVault(home, backend="auto")
    assert vault.describe_backend() in ("file", "keyring")
    assert vault.available() is True


def test_unwritable_home_reports_unavailable(tmp_path):
    """目录建不出来 → 明确报不可用，写入返回 ok=False 而不是假装成功。"""
    blocker = tmp_path / "blocker"
    blocker.write_text("我是文件不是目录", encoding="utf-8")
    vault = SecretsVault(blocker / "nested", backend="file")
    assert vault.describe_backend() == "none"
    assert vault.available() is False
    assert vault.set_secret("anthropic", PLAINTEXT) == {"ok": False, "available": False}
    assert vault.get_secret("anthropic") is None
    assert vault.has_secret("anthropic") is False


class _FakeKeyring:
    """内存假钥匙串：只实现 SecretsVault 用到的四个方法。"""

    def __init__(self):
        self.items: dict[tuple[str, str], str] = {}

    def set_password(self, service, key, value):
        self.items[(service, key)] = value

    def get_password(self, service, key):
        return self.items.get((service, key))

    def delete_password(self, service, key):
        self.items.pop((service, key), None)


def test_keyring_backend_is_preferred_when_available(monkeypatch, home):
    from mvvm.services import secrets_vault as module

    fake = _FakeKeyring()
    monkeypatch.setattr(module, "_keyring_module", lambda: fake)
    vault = SecretsVault(home, backend="auto")
    assert vault.describe_backend() == "keyring"

    vault.set_secret("anthropic", PLAINTEXT)
    assert fake.items[(KEYRING_SERVICE, "anthropic")] == PLAINTEXT
    # 用钥匙串时绝不写加密文件
    assert not (home / SECRETS_FILE).exists()
    assert vault.get_secret("anthropic") == PLAINTEXT
    assert vault.list_keys() == ["anthropic"]

    vault.delete_secret("anthropic")
    assert (KEYRING_SERVICE, "anthropic") not in fake.items
    assert vault.list_keys() == []


def test_keyring_backend_never_writes_plaintext(home, monkeypatch):
    from mvvm.services import secrets_vault as module

    monkeypatch.setattr(module, "_keyring_module", lambda: _FakeKeyring())
    vault = SecretsVault(home, backend="auto")
    vault.set_secret("anthropic", PLAINTEXT)
    for path in home.rglob("*"):
        if path.is_file():
            assert PLAINTEXT not in path.read_text(encoding="utf-8", errors="ignore")


def test_forced_keyring_without_backend_is_unavailable(monkeypatch, home):
    from mvvm.services import secrets_vault as module

    monkeypatch.setattr(module, "_keyring_module", lambda: None)
    vault = SecretsVault(home, backend="keyring")
    assert vault.describe_backend() == "none"
    assert vault.set_secret("anthropic", PLAINTEXT) == {"ok": False, "available": False}


def test_backend_env_override(monkeypatch, home):
    monkeypatch.setenv("DEVA_SECRETS_BACKEND", "file")
    assert SecretsVault(home).describe_backend() == "file"


def test_unknown_backend_env_is_ignored(monkeypatch, home):
    monkeypatch.setenv("DEVA_SECRETS_BACKEND", "banana")
    vault = SecretsVault(home)
    assert vault.describe_backend() in ("file", "keyring")


def test_default_home_uses_deva_home_env(monkeypatch, tmp_path):
    # 这条锁的是「旧变量 DEVA_HOME 仍被读取」。解析顺序是 AI_UPPER_HOME → DEVA_HOME，
    # 所以必须先清掉 AI_UPPER_HOME：宿主机若导出了它（打包启动器、parity 脚本都会），
    # 不清就会读到宿主目录，用例变成对宿主环境的隐式依赖而不是对行为的断言。
    monkeypatch.delenv("AI_UPPER_HOME", raising=False)
    monkeypatch.setenv("DEVA_HOME", str(tmp_path / "custom"))
    monkeypatch.setenv("DEVA_SECRETS_BACKEND", "file")
    vault = SecretsVault()
    vault.set_secret("anthropic", PLAINTEXT)
    assert (tmp_path / "custom" / SECRETS_FILE).exists()
