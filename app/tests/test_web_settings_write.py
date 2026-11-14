"""设置类写通道：桥入口 → 密钥库 / 配置 / 角色 / 技能 / 档案 / 模型清单。

和 `test_web_chat_write.py` 同一套做法：从桥的真实入口（`bridge._handlers[channel]`）调，
断言落盘结果与返回值，不绕过桥直接调服务。

两边都覆盖的原因：这些通道在渲染层里和对话写路径一样是**会改用户数据**的入口，
只测服务层就证明不了「渲染层调用形状 → 桥转换 → 落盘」这条链是通的。

模型清单探针用 `ScriptedTransport`（离线 `/models` 响应），不访问网络。
"""
from __future__ import annotations

import json
import time

import pytest

from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.persona_store import PersonaStore
from mvvm.services.secrets_vault import SecretsVault
from mvvm.services.settings_service import SettingsService
from mvvm.webui.bridge import DevaBridge

from helpers_png import png_bytes
from scripted_transport import ScriptedTransport

PNG_DATA_URI = "data:image/png;base64," + __import__("base64").b64encode(png_bytes()).decode()


@pytest.fixture()
def rig(tmp_path, monkeypatch):
    """真实桥 + 真实服务，密钥走后端为加密文件。"""
    monkeypatch.setenv("DEVA_SECRETS_BACKEND", "file")
    home = tmp_path / "deva-home"
    home.mkdir(parents=True, exist_ok=True)
    settings = SettingsService(home)
    vault = SecretsVault(home)
    bridge = DevaBridge(
        settings=settings,
        personas=PersonaStore(home),
        store=ChatSessionStore(home),
        home=home,
    )
    bridge.vault = vault

    class Rig:
        pass

    r = Rig()
    r.bridge, r.settings, r.vault, r.home = bridge, settings, vault, home
    return r


def call(rig, channel: str, *args):
    return rig.bridge._handlers[channel](*args)


# ── config:set ───────────────────────────────────────────────────────────
def test_config_set_merges_top_level_and_persists(rig):
    assert call(rig, "config:set", {"theme": "dark", "language": "en"}) == {"ok": True}
    # 再写一次另一个键：顶层浅合并，前一次的键不能被抹掉。
    assert call(rig, "config:set", {"layout": {"sidebar": "narrow"}}) == {"ok": True}

    saved = json.loads((rig.home / "config.json").read_text(encoding="utf-8"))
    assert saved["theme"] == "dark"
    assert saved["language"] == "en"
    assert saved["layout"] == {"sidebar": "narrow"}
    # 读回也一致（内存态与磁盘同一份）。
    assert call(rig, "config:get")["theme"] == "dark"


def test_config_set_none_deletes_key(rig):
    call(rig, "config:set", {"theme": "dark"})
    assert call(rig, "config:set", {"theme": None}) == {"ok": True}
    assert "theme" not in json.loads((rig.home / "config.json").read_text(encoding="utf-8"))


def test_config_set_rejects_non_object(rig):
    with pytest.raises(Exception) as excinfo:
        call(rig, "config:set", "not-an-object")
    assert "对象" in str(excinfo.value)


# ── secrets:set / delete / has / list / available ────────────────────────
def test_secrets_round_trip_through_vault(rig):
    assert call(rig, "secrets:set", "p1", "sk-abc") == {"ok": True, "available": True}
    assert call(rig, "secrets:has", "p1") is True
    assert call(rig, "secrets:list") == ["p1"]
    assert call(rig, "secrets:available") is True
    # 明文不得落盘：磁盘上只有密文文件。
    assert not (rig.home / "secrets.json").exists()
    assert (rig.home / "secrets.enc").exists()
    assert "sk-abc" not in (rig.home / "secrets.enc").read_text(encoding="utf-8", errors="ignore")


def test_secrets_set_empty_string_deletes(rig):
    call(rig, "secrets:set", "p1", "sk-abc")
    assert call(rig, "secrets:set", "p1", "") == {"ok": True, "available": True}
    assert call(rig, "secrets:has", "p1") is False
    assert call(rig, "secrets:list") == []


def test_secrets_delete_is_idempotent(rig):
    call(rig, "secrets:set", "p1", "sk-abc")
    assert call(rig, "secrets:delete", "p1") == {"ok": True}
    # 原版：键不存在也返回成功。
    assert call(rig, "secrets:delete", "p1") == {"ok": True}


def test_secrets_set_without_vault_reports_unavailable(rig):
    rig.bridge.vault = None
    assert call(rig, "secrets:set", "p1", "sk-abc") == {"ok": False, "available": False}


def test_secrets_delete_without_vault_raises(rig):
    rig.bridge.vault = None
    with pytest.raises(Exception) as excinfo:
        call(rig, "secrets:delete", "p1")
    assert "未接线" in str(excinfo.value)


# ── provider:list-models（异步通道）──────────────────────────────────────
class _Probe:
    """把 bridge.finish 的调用收起来，便于同步断言异步通道的结果。"""

    def __init__(self):
        self.calls = []

    def __call__(self, request_id, ok, payload):
        self.calls.append((request_id, ok, payload))


def _wait(predicate, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_list_models_returns_sorted_ids(rig):
    from mvvm.services.provider_setup import ModelGateway

    transport = ScriptedTransport(
        status=200,
        chunks=[json.dumps({"data": [{"id": "b-model"}, {"id": "a-model"}]}).encode()],
    )
    rig.bridge.model_gateway = ModelGateway(rig.settings, rig.vault, transport)
    probe = _Probe()
    rig.bridge.finish = probe

    rig.bridge._list_models("req-1", {"providerId": "p1", "adapter": "anthropic", "baseURL": "https://api.example.com"})
    assert _wait(lambda: probe.calls)
    request_id, ok, payload = probe.calls[0]
    assert (request_id, ok) == ("req-1", True)
    assert payload["ok"] is True
    assert list(payload["models"]) == ["a-model", "b-model"]
    # 探针走的是 /v1/models，且带上了密钥库里的密钥。
    assert transport.calls[0]["url"].endswith("/v1/models")
    assert transport.calls[0]["headers"]["x-api-key"] == ""


def test_list_models_uses_stored_key(rig):
    from mvvm.services.provider_setup import ModelGateway

    call(rig, "secrets:set", "p1", "sk-live")
    transport = ScriptedTransport(status=200, chunks=[b'{"data": [{"id": "m"}]}'])
    rig.bridge.model_gateway = ModelGateway(rig.settings, rig.vault, transport)
    probe = _Probe()
    rig.bridge.finish = probe

    rig.bridge._list_models("req-2", {"providerId": "p1", "adapter": "anthropic", "baseURL": "https://api.example.com"})
    assert _wait(lambda: probe.calls)
    assert transport.calls[0]["headers"]["x-api-key"] == "sk-live"


def test_list_models_failure_is_reported_not_faked(rig):
    from mvvm.services.provider_setup import ModelGateway

    transport = ScriptedTransport(status=401, chunks=[b'{"error": "bad key"}'])
    rig.bridge.model_gateway = ModelGateway(rig.settings, rig.vault, transport)
    probe = _Probe()
    rig.bridge.finish = probe

    rig.bridge._list_models("req-3", {"providerId": "p1", "adapter": "anthropic", "baseURL": "https://api.example.com"})
    assert _wait(lambda: probe.calls)
    _rid, ok, payload = probe.calls[0]
    assert ok is True  # 通道本身成功回送
    assert payload["ok"] is False  # 但探针结果是失败
    assert "鉴权失败" in payload["message"]


def test_list_models_without_gateway_is_unimplemented(rig):
    probe = _Probe()
    rig.bridge.finish = probe
    rig.bridge._list_models("req-4", {"providerId": "p1"})
    assert probe.calls == [("req-4", False, {"unimplemented": True, "message": "模型网关未接线"})]


# ── personas 写通道 ──────────────────────────────────────────────────────
def test_persona_upsert_creates_then_overwrites(rig):
    created = call(rig, "personas:upsert", {"name": "测试角色", "prompt": "你是测试助手。"})
    assert created["name"] == "测试角色"
    assert created["prompt"] == "你是测试助手。"
    pid = created["id"]
    assert (rig.home / "personas" / f"{pid}.md").exists()

    updated = call(rig, "personas:upsert", {"id": pid, "name": "改名后", "prompt": "新提示词。"})
    assert updated["id"] == pid
    assert updated["name"] == "改名后"
    # 覆盖写，不是新建第二个文件。
    assert len(list((rig.home / "personas").glob("*.md"))) == 1


def test_persona_upsert_blank_name_falls_back(rig):
    created = call(rig, "personas:upsert", {"name": "   "})
    assert created["name"] == "未命名提示词"


def test_persona_upsert_with_enabled_writes_flag(rig):
    created = call(rig, "personas:upsert", {"name": "启用角色", "enabled": True})
    listed = {p["id"]: p for p in call(rig, "personas:list")}
    assert listed[created["id"]]["enabled"] is True


def test_persona_set_enabled_and_reorder(rig):
    a = call(rig, "personas:upsert", {"name": "A"})["id"]
    b = call(rig, "personas:upsert", {"name": "B"})["id"]

    assert call(rig, "personas:set-enabled", a, True) == {"ok": True}
    assert call(rig, "personas:reorder", [b, a, b, "bad id", 3]) == {"ok": True}

    listed = [p["id"] for p in call(rig, "personas:list")]
    assert listed[:2] == [b, a]
    saved = json.loads((rig.home / "config.json").read_text(encoding="utf-8"))
    assert saved["personas"]["order"] == [b, a]
    assert saved["personas"]["enabled"][a] is True


def test_persona_remove_is_idempotent_and_cleans_config(rig):
    pid = call(rig, "personas:upsert", {"name": "待删"})["id"]
    call(rig, "personas:set-enabled", pid, True)
    assert call(rig, "personas:remove", pid) == {"ok": True}
    assert not (rig.home / "personas" / f"{pid}.md").exists()
    assert pid not in (rig.home / "config.json").read_text(encoding="utf-8")
    # 原版：非法 id / 不存在都回 ok。
    assert call(rig, "personas:remove", "不存在的id") == {"ok": True}
    assert call(rig, "personas:remove", pid) == {"ok": True}


def test_persona_avatar_round_trip(rig):
    pid = call(rig, "personas:upsert", {"name": "头像角色"})["id"]
    uri = call(rig, "personas:set-avatar-image", pid, PNG_DATA_URI)
    assert uri.startswith("data:image/png;base64,")
    assert (rig.home / "personas" / "avatars" / f"{pid}.png").exists()
    # list 里带 avatarImage（渲染层直接用）。
    listed = {p["id"]: p for p in call(rig, "personas:list")}
    assert listed[pid]["avatarImage"] == uri

    assert call(rig, "personas:clear-avatar-image", pid) == {"ok": True}
    assert not (rig.home / "personas" / "avatars" / f"{pid}.png").exists()


def test_persona_avatar_rejects_bad_payload(rig):
    pid = call(rig, "personas:upsert", {"name": "坏图"})["id"]
    assert call(rig, "personas:set-avatar-image", pid, "not a data uri") == ""
    assert call(rig, "personas:set-avatar-image", "bad id", PNG_DATA_URI) == ""


# ── skills 写通道 ────────────────────────────────────────────────────────
def _make_skill(rig, skill_id: str, name: str = "测试技能"):
    folder = rig.home / "skills" / skill_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: 测试用\n---\n正文\n", encoding="utf-8"
    )


def test_skill_set_enabled_toggles_and_persists(rig):
    _make_skill(rig, "my-skill")
    assert call(rig, "skills:set-enabled", "my-skill", False) == {"ok": True}
    listed = {s["id"]: s for s in call(rig, "skills:list")}
    assert listed["my-skill"]["enabled"] is False
    assert call(rig, "skills:set-enabled", "my-skill", True) == {"ok": True}
    assert {s["id"]: s for s in call(rig, "skills:list")}["my-skill"]["enabled"] is True


def test_skill_set_enabled_on_builtin_is_noop_but_ok(rig):
    from mvvm.services.skill_store import RESERVED_IDS

    builtin = sorted(RESERVED_IDS)[0]
    assert call(rig, "skills:set-enabled", builtin, False) == {"ok": True}
    saved = json.loads((rig.home / "config.json").read_text(encoding="utf-8")) if (rig.home / "config.json").exists() else {}
    assert builtin not in json.dumps(saved)


def test_skill_set_roles_normalizes(rig):
    _make_skill(rig, "role-skill")
    assert call(rig, "skills:set-roles", "role-skill", ["a", "", "a", 3, "b"]) == {"ok": True}
    listed = {s["id"]: s for s in call(rig, "skills:list")}
    assert listed["role-skill"]["roles"] == ["a", "b"]
    # null → 删除该键（= 全部角色）。
    assert call(rig, "skills:set-roles", "role-skill", None) == {"ok": True}
    assert {s["id"]: s for s in call(rig, "skills:list")}["role-skill"]["roles"] is None


def test_skill_set_roles_rejects_builtin(rig):
    from mvvm.services.skill_store import RESERVED_IDS

    builtin = sorted(RESERVED_IDS)[0]
    assert call(rig, "skills:set-roles", builtin, ["a"]) == {"ok": False}


def test_skill_remove_deletes_dir_and_toggles(rig):
    _make_skill(rig, "gone-skill")
    call(rig, "skills:set-enabled", "gone-skill", False)
    assert call(rig, "skills:remove", "gone-skill") == {"ok": True}
    assert not (rig.home / "skills" / "gone-skill").exists()
    assert "gone-skill" not in {
        s["id"] for s in call(rig, "skills:list") if s.get("source") != "builtin"
    }
    # 目录本就不存在视为成功；内置 id 拒绝。
    assert call(rig, "skills:remove", "gone-skill") == {"ok": True}
    from mvvm.services.skill_store import RESERVED_IDS

    assert call(rig, "skills:remove", sorted(RESERVED_IDS)[0]) == {"ok": False}


# ── profile 写通道 ───────────────────────────────────────────────────────
def test_profile_get_returns_default_avatar(rig):
    profile = call(rig, "profile:get")
    assert profile["avatar"].startswith('{"selections"')
    assert profile["avatarImage"] == ""


def test_profile_set_avatar_round_trip(rig):
    assert call(rig, "profile:set-avatar", '{"selections": {}}') == {"ok": True}
    assert call(rig, "profile:get")["avatar"] == '{"selections": {}}'


def test_profile_set_avatar_too_long_clears(rig):
    call(rig, "profile:set-avatar", '{"selections": {}}')
    huge = "x" * 5000
    assert call(rig, "profile:set-avatar", huge) == {"ok": True}
    # 超过 4096 字节 = 视为清除，回落默认头像。
    assert call(rig, "profile:get")["avatar"].startswith('{"selections"')


def test_profile_avatar_image_round_trip(rig):
    uri = call(rig, "profile:set-avatar-image", PNG_DATA_URI)
    assert uri.startswith("data:image/png;base64,")
    assert (rig.home / "profile" / "avatar.png").exists()
    assert call(rig, "profile:set-avatar-image", "") == ""
    assert not (rig.home / "profile" / "avatar.png").exists()
