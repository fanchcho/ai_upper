"""对话正文渲染：工具卡片、内联图片占位、待办胶囊文案（纯函数，不碰 Qt）。"""
from __future__ import annotations

import base64

from mvvm.views.transcript_render import (
    IMAGE_MAX_COUNT,
    IMAGE_URL_PREFIX,
    decode_images,
    todo_capsule_text,
    todo_item_lines,
    todo_now_text,
    transcript_html,
    transcript_plain_text,
)


def entry(role: str, text: str, **extra):
    return {"role": role, "text": text, **extra}


# ── 消息与转义 ─────────────────────────────────────────────────────────────
def test_plain_message_renders_role_head_and_body():
    html = transcript_html([entry("user", "你好"), entry("assistant", "在。")])
    assert "［你］" in html and "你好" in html
    assert "［助手］" in html and "在。" in html


def test_error_role_and_is_error_both_marked():
    """`error` 角色本身就叫「错误」；只有普通角色带 `is_error` 才加「（失败）」。"""
    html = transcript_html([entry("error", "网络断了"), entry("assistant", "半句", is_error=True)])
    assert "［错误］" in html
    assert "［助手（失败）］" in html
    assert "网络断了" in html


def test_html_special_characters_are_escaped():
    html = transcript_html([entry("user", "<script>alert(1)</script> & <b>")])
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&amp;" in html


def test_newlines_become_breaks_and_double_spaces_preserved():
    html = transcript_html([entry("user", "第一行\n第二行")])
    assert "第一行<br/>第二行" in html
    assert "x&nbsp;&nbsp;y" in transcript_html([entry("user", "x  y")])


# ── 工具卡 ────────────────────────────────────────────────────────────────
def test_tool_entry_becomes_a_card_with_name_and_status():
    html = transcript_html([entry("tool", "文件内容", name="read_file", summary="12 行")])
    assert "<table" in html
    assert "read_file · 12 行" in html
    assert "（成功）" in html
    assert "文件内容" in html


def test_failed_tool_card_is_marked():
    html = transcript_html([entry("tool", "拒绝访问", name="write_file", is_error=True)])
    assert "（失败）" in html
    assert "拒绝访问" in html


def test_tool_without_name_falls_back_to_generic_title():
    html = transcript_html([entry("tool", "结果")])
    assert "<b>工具</b>（成功）" in html


# ── 图片 ──────────────────────────────────────────────────────────────────
def _png_bytes() -> bytes:
    """1×1 PNG：读图分支的测试只要一个合法的图片魔数，不需要 Qt 解码。"""
    import struct
    import zlib

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
        + chunk(b"IEND", b"")
    )


def test_tool_image_gets_placeholder_url_and_caption():
    data = base64.b64encode(_png_bytes()).decode()
    images = [{"mediaType": "image/png", "name": "shot.png", "data": data}]
    html = transcript_html([entry("tool", "已读取图片", name="read_file", images=images)])
    assert f'src="{IMAGE_URL_PREFIX}0"' in html
    assert "［图片］shot.png" in html


def test_decode_images_returns_bytes_in_order():
    raw = _png_bytes()
    data = base64.b64encode(raw).decode()
    entries = [
        entry("user", "hi"),
        entry("tool", "图", images=[{"mediaType": "image/png", "data": data}]),
    ]
    assert decode_images(entries) == [("image/png", raw)]


def test_decode_images_skips_broken_payloads_without_shifting_index():
    good = base64.b64encode(_png_bytes()).decode()
    entries = [
        entry(
            "tool",
            "图",
            images=[
                {"mediaType": "image/png", "data": "not-base64!!"},
                {"mediaType": "image/png", "data": good},
                {"mediaType": "image/png"},
            ],
        )
    ]
    decoded = decode_images(entries)
    assert len(decoded) == 1 and decoded[0][0] == "image/png"


def test_images_beyond_the_cap_are_not_inlined():
    data = base64.b64encode(_png_bytes()).decode()
    images = [{"mediaType": "image/png", "name": f"{i}.png", "data": data} for i in range(IMAGE_MAX_COUNT + 2)]
    html = transcript_html([entry("tool", "多图", name="read_file", images=images)])
    assert html.count("<img") == IMAGE_MAX_COUNT


# ── 待办胶囊 ──────────────────────────────────────────────────────────────
STATE = {
    "id": "l1",
    "title": "迁移工具层",
    "items": [
        {"content": "读源码", "status": "completed"},
        {"content": "写实现", "status": "in_progress"},
        {"content": "补测试", "status": "pending"},
    ],
}


def test_capsule_shows_in_progress_item_and_counts():
    text = todo_capsule_text(STATE)
    assert "待办：迁移工具层" in text
    assert "写实现" in text
    assert "已完成 1/3" in text


def test_capsule_without_title_or_in_progress_item():
    state = {"items": [{"content": "第一步", "status": "pending"}]}
    assert todo_capsule_text(state) == "待办｜第一步（已完成 0/1）"
    assert todo_now_text({}) == ""


def test_capsule_hidden_when_no_active_list():
    assert todo_capsule_text(None) == ""
    assert todo_capsule_text({}) == ""


def test_capsule_falls_back_to_all_completed_title():
    state = {"title": "收尾", "items": [{"content": "a", "status": "completed"}]}
    assert todo_now_text(state) == ""
    assert todo_capsule_text(state) == "待办：收尾（已完成 1/1）"


def test_item_lines_use_status_marks():
    assert todo_item_lines(STATE) == ["[x] 读源码", "[~] 写实现", "[ ] 补测试"]


# ── 纯文本投影 ────────────────────────────────────────────────────────────
def test_plain_text_projection_matches_old_format():
    text = transcript_plain_text(
        [entry("user", "你好"), entry("tool", "内容", name="read_file", is_error=True)]
    )
    assert text == "[你] 你好\n\n[工具（失败） read_file] 内容"
