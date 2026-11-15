"""生成本轮逐页对比用的固定数据（只写目标目录，原版与 QML 两侧共用同一 DEVA_HOME）。

内容覆盖本轮要对比的正文形态：代码块（超长行 + 语言高亮）、表格、有序/无序/任务列表、
嵌套引用、分隔线、链接、图片。

用法: .venv/bin/python scripts/parity/make_pages_fixture.py <输出目录> [--sessions N]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# 会话时间必须相对「生成时刻」，不能写死绝对时间：原版与 QML 两侧显示的都是相对时间
# （useRelativeTime / time_label），写死 2026-11-14 那种绝对基准后，隔一天再截图，
# 原版说「21 hr ago」而 QML 说「yesterday」——两边数据一样，差别只是跑图的时间过去了。
# 这里把首条会话钉在「21 小时前」（离 24 小时边界还有 2 小时余量），其余按秒递减。
BASE = int(time.time() * 1000) - 22 * 3600 * 1000

LONG_LINE = "const value = [" + ", ".join('"item-%02d"' % i for i in range(24)) + "];"

CHAT_MD = """我先看一下目录，然后把结果整理成表格。

```python
def list_dir(path):
    return sorted(os.listdir(path))
```
""" + LONG_LINE + """

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `README.md` | 文档 | 项目用途与运行方式 |
| `src/` | 目录 | 源代码 |
| `package.json` | 配置 | 依赖清单 |

要点：

1. 先读 README
2. 再看依赖
3. 最后跑测试

- 无序项一
- 无序项二

- [x] 已完成
- [ ] 未完成

> 引用第一层
>
> > 嵌套引用第二层

---

参见[项目说明](https://example.com/docs)。

![示意图](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==)
"""


def session(session_id, title, text, updated, messages=None):
    return {
        "id": session_id,
        "title": title,
        "createdAt": BASE,
        "updatedAt": updated,
        "personaId": "general",
        "messages": messages
        or [
            {"role": "user", "content": "帮我看看这个目录里有什么，并说明 README 的用途。"},
            {"role": "assistant", "content": [{"type": "text", "text": text}]},
        ],
    }


def main(argv):
    out = Path(argv[1])
    count = 120
    if "--sessions" in argv:
        count = int(argv[argv.index("--sessions") + 1])
    chats = out / "data" / "chats"
    chats.mkdir(parents=True, exist_ok=True)

    index = []
    for i in range(count):
        sid = "parity-%03d" % i
        if i == 0:
            title, text = "对比用会话：一条完整回合", CHAT_MD
        else:
            title = "会话 %03d：准备发布说明" % i
            text = "这是第 %d 条会话的回复正文，用来验证长列表滚动与委托复用。" % i
        # 第 0 条（含代码块/表格的那条）排在最前：列表按 updatedAt 倒序，逐页对比要先看到它。
        updated = BASE + 60_000 + (count - i) * 1_000
        data = session(sid, title, text, updated)
        (chats / (sid + ".json")).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        index.append(
            {
                "id": sid,
                "title": title,
                "createdAt": BASE,
                "updatedAt": updated,
                "personaId": "general",
            }
        )
    (chats / "_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("fixture ok sessions=%d at %s" % (count, chats))


if __name__ == "__main__":
    main(sys.argv)
