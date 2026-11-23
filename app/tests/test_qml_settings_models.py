"""设置 › 模型 / 关于两页的数据投影（`mvvm.services.settings_models`）离线测试。

这些函数是设置页唯一的判据来源——QML 只负责画。上游对应的规则在
`features/settings/ModelSettings.tsx`（`visibleProviders` / `renderProviderRow` /
详情页）与 `shared/provider-headers.ts`（`headerIssue` / `sanitizeHeaders`）。
这里逐条锁住：过滤、行投影、详情投影、请求头行与写回。
"""
from __future__ import annotations

import copy

import pytest

from mvvm.services.provider_headers import MAX_CUSTOM_HEADERS
from mvvm.services.provider_registry import provider_headers
from mvvm.services.settings_models import (
    MODELS_TEXT,
    add_model,
    add_provider,
    header_rows,
    max_headers,
    models_text,
    new_provider,
    provider_detail,
    provider_entries,
    provider_row,
    provider_rows,
    remove_model,
    remove_provider,
    set_headers,
    set_model_enabled,
    update_provider,
    visible_providers,
)

# 一份覆盖各分支的配置：官方未启用无密钥（应隐藏）、官方已启用无密钥（灰点 + 告警）、
# 已存密钥但未启用（保留）、自定义（恒显）、决策模型（整体隐藏）。
MODELS = {
    "activeModelId": "relay:fast",
    "providers": [
        {"id": "hidden-off", "name": "Hidden Off", "purpose": "llm", "enabled": False, "models": []},
        {"id": "on-nokey", "name": "On No Key", "purpose": "llm", "enabled": True,
         "models": [{"id": "m1", "name": "m1", "enabled": True}]},
        {"id": "keyed-off", "name": "Keyed Off", "purpose": "llm", "enabled": False,
         "models": [{"id": "m2"}, {"id": "m3"}]},
        {"id": "relay", "name": "Relay", "kind": "custom", "purpose": "llm", "enabled": False,
         "headers": {"originator": "codex_cli", "User-Agent": " my-ua/1.0 "}, "models": []},
        {"id": "decision", "name": "Decision Model", "purpose": "decision", "enabled": True,
         "models": []},
    ],
}

KEYED = {"keyed-off"}


def has_key(provider_id: str) -> bool:
    return provider_id in KEYED


def _ids(section):
    return [p["id"] for p in provider_entries(section)]


@pytest.fixture(scope="module")
def models_qapp():
    # Reuse the provider interaction harness and its offscreen Qt setup.
    import test_qml_settings_provider  # noqa: F401
    from PySide6.QtGui import QGuiApplication

    application = QGuiApplication.instance() or QGuiApplication([])
    yield application


@pytest.mark.parametrize("enabled,keyed,warn", [
    (True, True, False), (True, False, True), (False, False, False),
])
def test_models_panel_structure_and_drilldown(
    models_qapp, tmp_path, monkeypatch, enabled, keyed, warn,
):
    """deva app.css:4475-4582 geometry + projected states + real pointer navigation.

    Use QML contexts to inspect the existing component IDs without adding a
    second view model or changing production objects just for test selectors.
    """
    from PySide6.QtQml import QQmlEngine, QQmlProperty
    from test_qml_settings_provider import _build_window, _click, _find_item, _pump

    window, bridge, settings, vault, ticker, engine = _build_window(
        tmp_path, monkeypatch, page="chat"
    )
    try:
        section = {"providers": [{
            "id": "p1", "kind": "custom", "purpose": "llm",
            "name": "Projected provider", "enabled": enabled,
            "models": [{"id": "first"}, {"id": "second"}],
        }]}
        settings.set_config({"models": section})
        if not keyed:
            vault.delete_secret("p1")
        window.setProperty("page", "settings-models")
        _pump(models_qapp, 0.6)
        add = _find_item(window.contentItem(), "modelsAddProvider")
        context = QQmlEngine.contextForObject(add)
        title = context.contextProperty("modTitle")
        head = title.parentItem()
        rows = context.contextProperty("modRows")
        listing = context.contextProperty("modList")
        pane = context.contextProperty("modPane")
        assert title.property("text") == "Providers"
        assert title.property("color").name() == "#1f1f24"
        assert title.property("font").pixelSize() == 15
        assert (head.x(), head.y(), head.height()) == (20, 16, 28)
        assert (add.width(), add.height(), add.property("radius")) == (28, 28, 8)
        assert QQmlProperty.read(add, "border.width") == 1
        assert QQmlProperty.read(add, "border.color").name() == "#e6e6ea"
        assert (rows.x(), rows.y(), rows.width(), rows.height()) == (20, 60, 510, 54)
        assert rows.property("radius") == 12
        assert QQmlProperty.read(rows, "border.width") == 1
        assert QQmlProperty.read(rows, "border.color").name() == "#e6e6ea"
        assert (listing.x(), listing.y(), listing.width(), listing.height()) == (1, 1, 508, 52)
        row = next(child for child in listing.property("contentItem").childItems()
                   if child.property("modelData") is not None)
        assert row.height() == 52
        projected = provider_rows(section, lambda _id: keyed, "en")
        assert bridge.modelRows() == projected
        assert row.property("modelData") == projected[0]
        row_context = QQmlEngine.contextForObject(row)
        main = row_context.contextProperty("providerMain")
        aside = row_context.contextProperty("providerAside")
        name, subtitle = main.childItems()
        assert (name.property("text"), subtitle.property("text")) == ("Projected provider", "2 models")
        assert main.x() == 36  # 14px padding + 10px dot + 12px gap
        dot = next(child for child in row.childItems() if child.width() == 10 and child.height() == 10)
        assert (dot.x(), dot.y()) == (14, 21)
        assert dot.property("color").name() == ("#2f9e44" if enabled else "#8a8a94")
        warning, chevron = aside.childItems()
        assert warning.property("visible") is warn
        assert (warning.property("size"), chevron.property("size")) == (14, 16)
        assert warning.property("color").name() == "#d9860b"
        assert chevron.property("visible") is True
        assert row.width() - aside.x() - aside.width() == 14
        _click(window, row)
        _pump(models_qapp, 0.2)
        assert pane.property("view") == "detail"
        assert pane.property("selectedId") == "p1"
        assert pane.property("detail") == bridge.providerDetail("p1")
        wrench = _find_item(window.contentItem(), "providerWrench")
        assert wrench.property("visible") is True
        _click(window, wrench)
        _pump(models_qapp, 0.2)
        assert pane.property("view") == "advanced"
        assert context.contextProperty("advancedView").property("visible") is True
        assert settings.models_section() == section, "Navigation must not mutate the provider data"
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()


# ── visible_providers：列表只列「在用」的 ───────────────────────────────────
def test_visible_providers_keeps_enabled_keyed_and_custom_only():
    ids = [p["id"] for p in visible_providers(MODELS, has_key)]
    # hidden-off 未启用且无密钥 → 隐藏；decision 整体隐藏（不进列表）。
    assert ids == ["on-nokey", "keyed-off", "relay"]


def test_visible_providers_hides_decision_purpose_even_when_enabled():
    section = {"providers": [{"id": "d", "purpose": "decision", "enabled": True, "kind": "custom"}]}
    assert visible_providers(section, lambda _p: True) == []


def test_visible_providers_treats_missing_purpose_as_llm():
    section = {"providers": [{"id": "legacy", "enabled": True}]}
    assert [p["id"] for p in visible_providers(section, lambda _p: False)] == ["legacy"]


@pytest.mark.parametrize("section", [None, {}, {"providers": None}, {"providers": "x"},
                                     {"providers": [1, "s", {"name": "no id"}]}])
def test_visible_providers_tolerates_garbage(section):
    assert visible_providers(section, has_key) == []


# ── provider_row：启用点 / 名称 / N models / 告警 ──────────────────────────
def test_provider_row_warns_only_when_enabled_without_key():
    on = provider_row(MODELS["providers"][1], has_key, "en")
    assert on == {"id": "on-nokey", "name": "On No Key", "enabled": True,
                  "detail": "1 models", "warn": True}
    # 未启用时即使没有密钥也不告警（没启用就不会发请求）。
    off = provider_row(MODELS["providers"][0], has_key, "en")
    assert off["enabled"] is False and off["warn"] is False


def test_provider_row_detail_is_localized_and_falls_back_to_id():
    row = provider_row({"id": "x-1", "enabled": True, "models": [{"id": "a"}, {"id": "b"}]}, has_key, "zh")
    assert row["name"] == "x-1"           # 没有 name 用 id
    assert row["detail"] == "2 个模型"     # 中文文案
    assert row["warn"] is True            # x-1 不在 KEYED 里 → 已启用但无密钥


def test_provider_rows_follows_visible_order():
    rows = provider_rows(MODELS, has_key, "en")
    assert [r["id"] for r in rows] == ["on-nokey", "keyed-off", "relay"]
    assert rows[2]["name"] == "Relay"


# ── 详情投影 ───────────────────────────────────────────────────────────────
def test_provider_detail_projects_models_and_flags():
    detail = provider_detail(MODELS, "keyed-off", "en", has_key)
    assert detail["id"] == "keyed-off"
    assert [m["id"] for m in detail["models"]] == ["m2", "m3"]
    assert detail["models"][0]["enabled"] is False       # 缺 enabled 视为关
    assert detail["advanced"] is True                    # 对话模型给扳手
    assert detail["canRename"] is False                  # 非 custom 不可改名
    assert detail["warn"] is False                       # 未启用


def test_provider_detail_show_id_only_when_name_differs():
    section = {"providers": [{"id": "p", "enabled": True, "models": [
        {"id": "gpt-4o", "name": "gpt-4o"}, {"id": "gpt-4o", "name": "Fast"},
    ]}]}
    models = provider_detail(section, "p", "en", has_key)["models"]
    assert [m["showId"] for m in models] == [False, True]


def test_provider_detail_advanced_hidden_for_decision_purpose():
    detail = provider_detail(MODELS, "decision", "en", has_key)
    assert detail["advanced"] is False      # 决策模型不给扳手（不经 providerHeaders）
    # `warn` 与列表行同一条判定（已启用且无密钥），只是这个详情页在列表里不可达。
    assert detail["warn"] is True


def test_provider_detail_warn_matches_row_rule():
    detail = provider_detail(MODELS, "on-nokey", "en", has_key)
    assert detail["warn"] is True and detail["enabled"] is True


def test_provider_detail_custom_can_rename_and_carries_header_rows():
    detail = provider_detail(MODELS, "relay", "en", has_key)
    assert detail["canRename"] is True
    assert detail["kind"] == "custom"
    assert [h["name"] for h in detail["headers"]] == ["originator", "User-Agent"]


def test_provider_detail_returns_none_for_unknown_id():
    assert provider_detail(MODELS, "nope", "en", has_key) is None


# ── 请求头行：三种原因 + 文案 ──────────────────────────────────────────────
def test_header_rows_marks_name_reserved_and_value_reasons():
    rows = header_rows(
        {"bad name": "v", "Authorization": "Bearer x", "x-cjk": "中文", "ok": "fine"},
        "en",
    )
    by_name = {r["name"]: r for r in rows}
    assert by_name["bad name"]["issue"] == "name"
    assert by_name["Authorization"]["issue"] == "reserved"
    assert by_name["x-cjk"]["issue"] == "value"
    assert by_name["ok"]["issue"] == "" and by_name["ok"]["issueText"] == ""
    # 界面直接显示的文案来自 MODELS_TEXT，不在这里现拼。
    assert by_name["bad name"]["issueText"] == MODELS_TEXT["en"]["headerIssue"]["name"]


def test_header_rows_tolerates_non_dict_and_none_value():
    assert header_rows(None, "en") == []
    rows = header_rows({"x-a": None}, "en")
    assert rows == [{"name": "x-a", "value": "", "issue": "", "issueText": ""}]


def test_header_rows_uses_chinese_issue_text():
    rows = header_rows({"bad name": "v"}, "zh")
    assert rows[0]["issueText"] == MODELS_TEXT["zh"]["headerIssue"]["name"]


def test_max_headers_matches_provider_headers_limit():
    assert max_headers() == MAX_CUSTOM_HEADERS == 32


# ── 文案表 ─────────────────────────────────────────────────────────────────
def test_text_tables_have_the_same_keys_both_languages():
    zh, en = MODELS_TEXT["zh"], MODELS_TEXT["en"]
    assert set(zh) == set(en)
    assert set(zh["headerIssue"]) == set(en["headerIssue"]) == {"name", "reserved", "value"}


def test_models_text_is_a_copy_and_falls_back_to_english():
    text = models_text("zh")
    text["providers"] = "MUTATED"
    assert MODELS_TEXT["zh"]["providers"] != "MUTATED"
    assert models_text("fr")["providers"] == MODELS_TEXT["en"]["providers"]


# ── 写回 ───────────────────────────────────────────────────────────────────
def test_update_provider_patches_without_touching_the_input():
    before = copy.deepcopy(MODELS)
    updated = update_provider(MODELS, "on-nokey", {"name": "Renamed", "enabled": False})
    assert updated["providers"][1]["name"] == "Renamed"
    assert updated["providers"][1]["enabled"] is False
    assert MODELS == before                       # 入参不被改（深拷贝）
    assert updated is not MODELS


def test_update_provider_none_drops_the_key():
    updated = update_provider(MODELS, "relay", {"apiHost": None})
    assert "apiHost" not in updated["providers"][3]


def test_update_provider_unknown_id_returns_none():
    assert update_provider(MODELS, "nope", {"name": "x"}) is None


def test_remove_provider_and_active_model_cleanup():
    updated = remove_provider(MODELS, "relay")
    assert "relay" not in _ids(updated)
    assert "activeModelId" not in updated         # 指向被删服务商 → 一并清掉
    assert MODELS["activeModelId"] == "relay:fast"  # 入参不改


def test_remove_provider_keeps_unrelated_active_model():
    updated = remove_provider(MODELS, "relay")
    section = dict(updated, activeModelId="on-nokey:m1")
    assert remove_provider(section, "keyed-off")["activeModelId"] == "on-nokey:m1"


def test_remove_provider_unknown_returns_none():
    assert remove_provider(MODELS, "nope") is None
    assert remove_provider({}, "relay") is None


def test_add_provider_appends_and_deep_copies():
    provider = new_provider({}, "custom-1", "Custom")
    updated = add_provider(MODELS, provider)
    assert _ids(updated)[-1] == "custom-1"
    updated["providers"][-1]["name"] = "Changed"
    assert provider["name"] == "Custom"


def test_add_provider_replaces_same_id_in_place():
    updated = add_provider(MODELS, new_provider({}, "on-nokey", "Replaced"))
    assert _ids(updated).count("on-nokey") == 1
    assert updated["providers"][1]["name"] == "Replaced"


def test_new_provider_shape_matches_upstream_custom_defaults():
    provider = new_provider({}, "custom-1", "Custom", accent="#123456")
    assert provider == {
        "id": "custom-1", "name": "Custom", "kind": "custom", "purpose": "llm",
        "accent": "#123456", "adapter": "openai", "apiHost": "", "enabled": True,
        "models": [],
    }


def test_set_headers_sanitizes_and_writes_lowercase_table():
    updated = set_headers(MODELS, "on-nokey", {"Originator": " codex ", "n": ""})
    assert updated["providers"][1]["headers"] == {"originator": "codex"}


def test_set_headers_drops_the_key_when_nothing_valid_remains():
    updated = set_headers(MODELS, "relay", {"authorization": "Bearer x", "bad name": "v"})
    assert "headers" not in updated["providers"][3]


def test_set_headers_caps_rows_at_the_upstream_limit():
    raw = {f"x-h{i}": "v" for i in range(MAX_CUSTOM_HEADERS + 5)}
    updated = set_headers({"providers": [{"id": "p"}]}, "p", raw)
    written = updated["providers"][0]["headers"]
    assert len(written) == MAX_CUSTOM_HEADERS
    assert list(written)[:2] == ["x-h0", "x-h1"]


def test_set_headers_unknown_provider_returns_none():
    assert set_headers(MODELS, "nope", {"a": "b"}) is None
    assert set_headers({}, "p", {"a": "b"}) is None


def test_set_headers_last_wins_on_duplicate_names():
    # 行 → dict 由桥层按名归并；这里直接给表，验证大小写归一时后写覆盖。
    updated = set_headers({"providers": [{"id": "p"}]}, "p",
                          {"User-Agent": "a", "user-agent": "b"})
    assert updated["providers"][0]["headers"] == {"user-agent": "b"}


def test_set_model_enabled_flips_only_the_target_model():
    updated = set_model_enabled(MODELS, "keyed-off", "m3", True)
    assert [m.get("enabled") for m in updated["providers"][2]["models"]] == [None, True]
    assert set_model_enabled(MODELS, "keyed-off", "missing", True) is None
    assert set_model_enabled(MODELS, "nope", "m2", True) is None


def test_add_model_dedupes_and_requires_non_empty_id():
    updated = add_model(MODELS, "keyed-off", " m4 ")
    assert [m["id"] for m in updated["providers"][2]["models"]] == ["m2", "m3", "m4"]
    added = updated["providers"][2]["models"][-1]
    assert added == {"id": "m4", "name": "m4", "enabled": True}
    assert add_model(MODELS, "keyed-off", "m2") is None       # 去重
    assert add_model(MODELS, "keyed-off", "   ") is None      # 空 id


def test_add_model_creates_the_list_when_missing():
    updated = add_model({"providers": [{"id": "p"}]}, "p", "m1")
    assert updated["providers"][0]["models"] == [{"id": "m1", "name": "m1", "enabled": True}]


def test_remove_model_and_active_model_cleanup():
    section = dict(copy.deepcopy(MODELS), activeModelId="keyed-off:m3")
    updated = remove_model(section, "keyed-off", "m3")
    assert [m["id"] for m in updated["providers"][2]["models"]] == ["m2"]
    assert "activeModelId" not in updated
    assert remove_model(MODELS, "keyed-off", "missing") is None


# ── 与发请求侧对位：自定义头最后合并、同名覆盖默认 user-agent ────────────────
def test_provider_headers_applies_custom_headers_last_and_overrides_user_agent():
    headers = provider_headers("https://api.example.com", provider_id="relay", models_section=MODELS)
    assert headers["user-agent"] == "my-ua/1.0"     # 自定义头覆盖默认 UA
    assert headers["originator"] == "codex_cli"


def test_provider_headers_without_custom_rows_keeps_the_default_user_agent():
    headers = provider_headers("https://api.example.com", provider_id="on-nokey", models_section=MODELS)
    assert headers["user-agent"].startswith("deva/")


def test_written_headers_are_exactly_what_gets_sent():
    """界面写进去的表 = 下一次请求会发的表（同一份 sanitize 规则）。"""
    updated = set_headers({"providers": [{"id": "p"}]}, "p",
                          {" Originator ": " codex ", "authorization": "leak"})
    headers = provider_headers("https://api.example.com", provider_id="p", models_section=updated)
    assert headers["originator"] == "codex"
    assert "authorization" not in headers
