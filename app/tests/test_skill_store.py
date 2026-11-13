"""技能服务：目录扫描、frontmatter 解析、内置元技能、启用/角色配置语义。

对应 Deva `services/skills.ts` + `services/frontmatter.ts` + `services/ext-roles.ts`。
这几条语义渲染层直接依赖，改错会让「设置 › 扩展」页与原版不一致：
- 目录不存在时也要返回内置技能（首启页不能误显空态）；
- 同名磁盘目录不得影子内置技能；
- 启用态取 `config.json` 的 `skills.enabled[id]`，缺失即启用；
- 角色取 `skills.roles[id]`，缺失 = 全部角色（None）。
"""
from __future__ import annotations

import json

import pytest

from mvvm.services.skill_store import (
    BUILTIN_SKILLS,
    SkillStore,
    fm_array,
    parse_frontmatter,
)


@pytest.fixture()
def store(tmp_path):
    return SkillStore(tmp_path / "deva-home")


def write_skill(home, skill_id, text):
    folder = home / "skills" / skill_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(text, encoding="utf-8")


def write_config(home, data):
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.json").write_text(json.dumps(data), encoding="utf-8")


# ── 内置技能 ──────────────────────────────────────────────────────────────
def test_builtins_returned_before_dir_exists(store):
    skills = store.list_skills()
    assert [s["id"] for s in skills] == ["create-skill", "create-agent", "create-mcp"]
    assert all(s["source"] == "builtin" and s["enabled"] and s["roles"] is None for s in skills)
    assert store.dir.exists() is False


def test_builtin_instructions_are_non_empty_and_distinct():
    bodies = [s["instructions"] for s in BUILTIN_SKILLS]
    assert all(len(b) > 500 for b in bodies)
    assert len(set(bodies)) == 3


def test_builtin_get_returns_copy(store):
    first = store.get("create-skill")
    first["enabled"] = False
    assert store.get("create-skill")["enabled"] is True


def test_disk_dir_cannot_shadow_builtin(store, tmp_path):
    home = tmp_path / "deva-home"
    write_skill(home, "create-skill", "---\nname: 假的\n---\n正文")
    assert [s["id"] for s in store.list_skills()] == [
        "create-skill",
        "create-agent",
        "create-mcp",
    ]
    assert store.get("create-skill")["source"] == "builtin"


def test_builtin_get_unknown_id_is_none(store):
    assert store.get("no-such-skill") is None


# ── 目录扫描 ──────────────────────────────────────────────────────────────
def test_custom_skills_sorted_by_name_after_builtins(store, tmp_path):
    home = tmp_path / "deva-home"
    write_skill(home, "beta", "---\nname: Zebra\n---\nB")
    write_skill(home, "alpha", "---\nname: apple\n---\nA")
    skills = store.list_skills()
    assert [s["id"] for s in skills] == ["create-skill", "create-agent", "create-mcp", "alpha", "beta"]
    assert skills[-1]["name"] == "Zebra"
    assert skills[-2]["name"] == "apple"


def test_missing_or_unreadable_skill_md_is_skipped(store, tmp_path):
    home = tmp_path / "deva-home"
    (home / "skills" / "empty-dir").mkdir(parents=True)
    write_skill(home, "good", "---\nname: Good\n---\nbody")
    (home / "skills" / "a-file").write_text("not a dir", encoding="utf-8")
    assert [s["id"] for s in store.list_skills()] == [
        "create-skill",
        "create-agent",
        "create-mcp",
        "good",
    ]


def test_unsafe_dir_names_are_ignored(store, tmp_path):
    home = tmp_path / "deva-home"
    write_skill(home, ".hidden", "---\nname: Hidden\n---\nX")
    write_skill(home, "ok-name", "---\nname: Ok\n---\nX")
    assert [s["id"] for s in store.list_skills()][-1] == "ok-name"
    assert all(s["id"] != ".hidden" for s in store.list_skills())


# ── 启用态 / 角色 ─────────────────────────────────────────────────────────
def test_enabled_defaults_true_and_false_from_config(store, tmp_path):
    home = tmp_path / "deva-home"
    write_skill(home, "on-default", "---\nname: D\n---\nX")
    write_skill(home, "off", "---\nname: O\n---\nX")
    write_config(home, {"skills": {"enabled": {"off": False}}})
    flags = {s["id"]: s["enabled"] for s in store.list_skills()}
    assert flags["on-default"] is True
    assert flags["off"] is False


def test_roles_missing_means_all_roles(store, tmp_path):
    home = tmp_path / "deva-home"
    write_skill(home, "any", "---\nname: Any\n---\nX")
    write_skill(home, "picked", "---\nname: Picked\n---\nX")
    write_config(home, {"skills": {"roles": {"picked": ["coder", "writer", 7]}}})
    roles = {s["id"]: s["roles"] for s in store.list_skills()}
    assert roles["any"] is None
    assert roles["picked"] == ["coder", "writer"]


def test_broken_config_json_does_not_break_listing(store, tmp_path):
    home = tmp_path / "deva-home"
    write_skill(home, "s", "---\nname: S\n---\nX")
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.json").write_text("{not json", encoding="utf-8")
    skills = store.list_skills()
    assert skills[-1]["id"] == "s"
    assert skills[-1]["enabled"] is True


# ── frontmatter ───────────────────────────────────────────────────────────
def test_parse_frontmatter_scalars_arrays_lists_and_maps():
    raw = (
        "---\n"
        'name: "My Skill"\n'
        "description: plain text\n"
        "allowed-tools: [read_file, write_file]\n"
        "tags:\n"
        "  - alpha\n"
        "  - beta\n"
        "metadata:\n"
        "  version: 2\n"
        "  owner: me\n"
        "---\n"
        "\n"
        "Body line 1\n"
        "Body line 2\n"
    )
    data, body = parse_frontmatter(raw)
    assert data["name"] == "My Skill"
    assert data["description"] == "plain text"
    assert data["allowed-tools"] == ["read_file", "write_file"]
    assert data["tags"] == ["alpha", "beta"]
    assert data["metadata"] == {"version": "2", "owner": "me"}
    assert body == "Body line 1\nBody line 2\n"


def test_parse_frontmatter_without_header_returns_whole_text():
    raw = "just a body\nno frontmatter"
    data, body = parse_frontmatter(raw)
    assert data == {}
    assert body == raw


def test_parse_frontmatter_unterminated_returns_whole_text():
    raw = "---\nname: x\nbody without closing"
    data, body = parse_frontmatter(raw)
    assert data == {}
    assert body == raw


def test_parse_frontmatter_escaped_quotes_and_bom():
    raw = '---\nname: "a \\"quoted\\" name"\n---\nBody'
    data, body = parse_frontmatter("﻿" + raw)
    assert data["name"] == 'a "quoted" name'
    assert body == "Body"


def test_fm_array_splits_scalar_but_respects_parens():
    data = {"allowed-tools": "Bash(git add:*) Bash(git commit:*) read_file"}
    assert fm_array(data, "allowed-tools") == [
        "Bash(git add:*)",
        "Bash(git commit:*)",
        "read_file",
    ]
    assert fm_array({"x": "a, b ,, c"}, "x") == ["a", "b", "c"]
    assert fm_array({}, "x") == []


def test_parse_skill_shape_matches_preload_contract(store, tmp_path):
    home = tmp_path / "deva-home"
    write_skill(
        home,
        "demo",
        "---\n"
        "name: Demo\n"
        "description: desc\n"
        "trigger: trig\n"
        "allowed-tools: [read_file]\n"
        "license: MIT\n"
        "compatibility: any\n"
        "---\n"
        "\n"
        "Use it.\n",
    )
    skill = store.get("demo")
    assert skill == {
        "id": "demo",
        "name": "Demo",
        "description": "desc",
        "trigger": "trig",
        "allowedTools": ["read_file"],
        "license": "MIT",
        "compatibility": "any",
        "metadata": {},
        "instructions": "Use it.",
        "enabled": True,
        "roles": None,
        "source": "custom",
    }


def test_parse_skill_falls_back_to_id_as_name(store, tmp_path):
    home = tmp_path / "deva-home"
    write_skill(home, "no-name", "---\ndescription: d\n---\nX")
    assert store.get("no-name")["name"] == "no-name"


def test_unsafe_get_id_is_none(store):
    assert store.get("../../etc/passwd") is None
    assert store.get("..") is None
