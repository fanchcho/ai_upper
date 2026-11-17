"""角色与技能的写路径：落盘语义、边界与「失败恒回 ok」口径。

**为什么存在**：原 `app/tests/test_web_settings_write.py` 经已删除的 `DevaBridge`
（QtWebChannel）调用同一批服务方法。桥删掉后那批用例消失，但
`PersonaStore` / `SkillStore` 的写方法**仍在生产路径上**——QML 壳的
`setSkillEnabled` 等入口写的就是 `skills.enabled[id]` 这一层。本文件把
「不是通道形状、而是服务写语义」的部分接回来，入口改为直接调服务方法。

`SettingsService` 与 `SecretsVault` 的同类覆盖已分别在
`test_settings_service.py`（16 条）与 `test_secrets_vault.py`（21 条）里，
这里不重复；`SkillStore` 的读路径在 `test_skill_store.py`（19 条）。
缺口只剩两处写路径：角色写入（`PersonaStore` 此前无任何直接用例）与技能写入。
"""
from __future__ import annotations

import base64
import json

import pytest

from mvvm.services.persona_store import PersonaStore, is_safe_id
from mvvm.services.skill_store import BUILTIN_SKILLS, SkillStore

from helpers_png import png_bytes

PNG_DATA_URI = "data:image/png;base64," + base64.b64encode(png_bytes()).decode()


@pytest.fixture()
def home(tmp_path):
    path = tmp_path / "deva-home"
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture()
def personas(home):
    return PersonaStore(home)


@pytest.fixture()
def skills(home):
    return SkillStore(home)


def read_config(home):
    return json.loads((home / "config.json").read_text(encoding="utf-8"))


def write_persona(home, persona_id, text):
    folder = home / "personas"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{persona_id}.md").write_text(text, encoding="utf-8")


def write_skill(home, skill_id, text="---\nname: Demo\n---\nbody\n"):
    folder = home / "skills" / skill_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(text, encoding="utf-8")


# ── PersonaStore.upsert ──────────────────────────────────────────────────
def test_persona_upsert_creates_file_and_returns_record(personas, home):
    record = personas.upsert({"name": "排版助手", "prompt": "你是排版助手。", "description": "d"})
    assert record["name"] == "排版助手"
    assert record["prompt"] == "你是排版助手。"
    assert record["description"] == "d"
    assert record["enabled"] is False  # 新建未传 enabled → 缺省关闭
    persona_id = record["id"]
    assert (home / "personas" / f"{persona_id}.md").is_file()
    assert personas.get(persona_id)["name"] == "排版助手"


def test_persona_upsert_blank_name_falls_back(personas):
    assert personas.upsert({"name": "   "})["name"] == "未命名提示词"
    assert personas.upsert({})["name"] == "未命名提示词"


def test_persona_upsert_overwrites_existing_id(personas):
    first = personas.upsert({"name": "One", "prompt": "a"})
    second = personas.upsert({"id": first["id"], "name": "Two", "prompt": "b"})
    assert second["id"] == first["id"]
    assert second["name"] == "Two"
    assert second["prompt"] == "b"
    assert [p["id"] for p in personas.list_personas()] == [first["id"]]


def test_persona_upsert_unsafe_id_generates_a_new_one(personas):
    existing = personas.upsert({"name": "Keep"})
    other = personas.upsert({"id": "../evil", "name": "Other"})
    assert other["id"] != "../evil"
    assert is_safe_id(other["id"])
    assert other["id"] != existing["id"]


def test_persona_upsert_with_enabled_writes_flag(personas, home):
    record = personas.upsert({"name": "On", "prompt": "p", "enabled": True})
    assert record["enabled"] is True
    assert read_config(home)["personas"]["enabled"][record["id"]] is True


def test_persona_upsert_non_object_payload_is_treated_as_empty(personas):
    record = personas.upsert(["not", "a", "dict"])
    assert record["name"] == "未命名提示词"


def test_persona_upsert_multiline_values_are_flattened(personas):
    record = personas.upsert({"name": "A\nB", "description": "x\ny"})
    assert record["name"] == "A B"
    assert record["description"] == "x y"


# ── PersonaStore.set_enabled / reorder ───────────────────────────────────
def test_persona_set_enabled_toggles_and_persists(personas, home):
    write_persona(home, "alpha", "---\nname: Alpha\n---\nbody\n")
    personas.set_enabled("alpha", True)
    assert personas.get("alpha")["enabled"] is True
    personas.set_enabled("alpha", False)
    assert personas.get("alpha")["enabled"] is False


def test_persona_set_enabled_on_unsafe_id_is_ok_without_writing(personas, home):
    assert personas.set_enabled("../evil", True) == {"ok": True}
    assert not (home / "config.json").exists()


def test_persona_reorder_sorts_and_filters_invalid_ids(personas, home):
    for pid in ("a", "b", "c"):
        write_persona(home, pid, f"---\nname: {pid}\n---\n")
    personas.reorder(["c", "../evil", "a", "c", 7])
    assert read_config(home)["personas"]["order"] == ["c", "a"]
    assert [p["id"] for p in personas.list_personas()] == ["c", "a", "b"]


def test_persona_reorder_non_list_resets_order(personas, home):
    write_persona(home, "a", "---\nname: a\n---\n")
    personas.reorder("not-a-list")
    assert read_config(home)["personas"]["order"] == []


# ── PersonaStore.remove / 头像 ───────────────────────────────────────────
def test_persona_remove_deletes_file_and_config_entries(personas, home):
    record = personas.upsert({"name": "Doomed", "prompt": "p", "enabled": True})
    personas.reorder([record["id"]])
    assert personas.remove(record["id"]) == {"ok": True}
    assert not (home / "personas" / f"{record['id']}.md").exists()
    assert record["id"] not in read_config(home)["personas"].get("enabled", {})
    assert record["id"] not in read_config(home)["personas"].get("order", [])


def test_persona_remove_is_idempotent_and_unsafe_id_is_ok(personas):
    assert personas.remove("missing") == {"ok": True}
    assert personas.remove("../evil") == {"ok": True}


def test_persona_avatar_round_trip(personas, home):
    write_persona(home, "alpha", "---\nname: Alpha\n---\n")
    assert personas.set_avatar_image("alpha", PNG_DATA_URI) == PNG_DATA_URI
    assert personas.get("alpha")["avatarImage"] == PNG_DATA_URI
    assert (home / "personas" / "avatars" / "alpha.png").is_file()


def test_persona_avatar_rejects_bad_payload(personas, home):
    write_persona(home, "alpha", "---\nname: Alpha\n---\n")
    assert personas.set_avatar_image("alpha", "data:image/gif;base64,AAAA") == ""
    assert personas.set_avatar_image("alpha", "not-a-data-uri") == ""
    assert personas.set_avatar_image("../evil", PNG_DATA_URI) == ""
    assert not (home / "personas" / "avatars").exists()


def test_persona_avatar_write_replaces_other_extensions(personas, home):
    write_persona(home, "alpha", "---\nname: Alpha\n---\n")
    avatars = home / "personas" / "avatars"
    avatars.mkdir(parents=True, exist_ok=True)
    (avatars / "alpha.webp").write_bytes(b"stale")
    assert personas.set_avatar_image("alpha", PNG_DATA_URI) == PNG_DATA_URI
    assert not (avatars / "alpha.webp").exists()
    assert (avatars / "alpha.png").is_file()


def test_persona_clear_avatar_image_removes_all_extensions(personas, home):
    write_persona(home, "alpha", "---\nname: Alpha\n---\n")
    personas.set_avatar_image("alpha", PNG_DATA_URI)
    assert personas.clear_avatar_image("alpha") == {"ok": True}
    assert personas.get("alpha")["avatarImage"] == ""
    assert personas.clear_avatar_image("../evil") == {"ok": True}


# ── PersonaStore 读路径的容错 ────────────────────────────────────────────
def test_persona_list_skips_unreadable_and_unsafe_files(personas, home):
    write_persona(home, "good", "---\nname: Good\n---\nbody\n")
    write_persona(home, "../evil", "---\nname: Evil\n---\n")
    (home / "personas" / "notes.txt").write_text("not a persona", encoding="utf-8")
    assert [p["id"] for p in personas.list_personas()] == ["good"]


def test_persona_list_missing_dir_is_empty(personas):
    assert personas.list_personas() == []


def test_persona_get_unsafe_id_is_none(personas):
    assert personas.get("../evil") is None


def test_persona_enabled_false_when_config_is_corrupt(personas, home):
    write_persona(home, "alpha", "---\nname: Alpha\n---\n")
    (home / "config.json").write_text("{not json", encoding="utf-8")
    assert personas.get("alpha")["enabled"] is False


# ── SkillStore 写路径 ────────────────────────────────────────────────────
def test_skill_set_enabled_toggles_and_persists(skills, home):
    write_skill(home, "demo")
    skills.set_enabled("demo", False)
    assert skills.get("demo")["enabled"] is False
    skills.set_enabled("demo", True)
    assert skills.get("demo")["enabled"] is True


def test_skill_set_enabled_on_builtin_is_noop_but_ok(skills, home):
    builtin_id = BUILTIN_SKILLS[0]["id"]
    assert skills.set_enabled(builtin_id, False) == {"ok": True}
    assert not (home / "config.json").exists()
    assert skills.get(builtin_id)["enabled"] is True


def test_skill_set_roles_normalizes_duplicates_and_blanks(skills, home):
    write_skill(home, "demo")
    assert skills.set_roles("demo", ["general", "", "general", 5, "coder"]) == {"ok": True}
    assert read_config(home)["skills"]["roles"]["demo"] == ["general", "coder"]
    assert skills.get("demo")["roles"] == ["general", "coder"]


def test_skill_set_roles_null_clears_the_entry(skills, home):
    write_skill(home, "demo")
    skills.set_roles("demo", ["general"])
    skills.set_roles("demo", None)
    assert "demo" not in read_config(home)["skills"]["roles"]
    assert skills.get("demo")["roles"] is None


def test_skill_set_roles_rejects_builtin_and_unsafe_ids(skills):
    assert skills.set_roles(BUILTIN_SKILLS[0]["id"], ["general"]) == {"ok": False}
    assert skills.set_roles("../evil", ["general"]) == {"ok": False}


def test_skill_remove_deletes_dir_and_config_entries(skills, home):
    write_skill(home, "demo")
    skills.set_enabled("demo", False)
    skills.set_roles("demo", ["general"])
    assert skills.remove("demo") == {"ok": True}
    assert not (home / "skills" / "demo").exists()
    section = read_config(home)["skills"]
    assert "demo" not in section.get("enabled", {})
    assert "demo" not in section.get("roles", {})


def test_skill_remove_missing_dir_still_cleans_config(skills, home):
    skills.set_enabled("ghost", False)
    assert skills.remove("ghost") == {"ok": True}
    assert "ghost" not in read_config(home)["skills"].get("enabled", {})


def test_skill_remove_rejects_builtin_and_unsafe_ids(skills, home):
    (home / "skills").mkdir(parents=True, exist_ok=True)
    (home / "evil").mkdir()  # `../evil` 若被当成路径就会落到这里
    assert skills.remove(BUILTIN_SKILLS[0]["id"]) == {"ok": False}
    assert skills.remove("../evil") == {"ok": False}
    assert (home / "evil").is_dir()  # 目录必须原样留着：非法 id 不删任何东西


def test_skill_writes_survive_corrupt_config(skills, home):
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.json").write_text("{not json", encoding="utf-8")
    write_skill(home, "demo")
    assert skills.set_enabled("demo", False) == {"ok": True}
    assert read_config(home)["skills"]["enabled"]["demo"] is False
