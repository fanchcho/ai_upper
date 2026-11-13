# 构建进度台账（每轮更新）

> 规则：只写**实际跑出来的**结果。命令与输出都是真的，没跑过的一律归入「写了没验证」或「没做」。
> 最近更新：2026-11-13（第一阶段骨架轮）

## 0. 本轮一句话结论

骨架能起，有一条纵向切片真跑通（发送 → 假 provider → 工具允许/拒绝 → 落盘 → 重启读回）。
全量测试 **428 passed / 5 skipped**（基线 377 全绿，新增 51 例）。真实窗口的会话列表、设置页、
真实网络 provider 均**未做**。

## 1. 已跑通（有可复现命令与真实输出）

| # | 项 | 验证方式 | 补充 |
|---|---|---|---|
| 1 | 会话持久化：建会话 / 追加消息 / 重启读回 | `pytest app/tests/test_chat_session_store.py -q` → `16 passed` | 一对话一文件 + `_index.json`；重启用全新 Store 实例，不是清缓存假装 |
| 2 | 索引自愈（缺失 / 损坏 → 扫描重建） | 同文件 `test_index_is_rebuilt_*`、`test_corrupt_index_falls_back_to_scan` | 单个坏文件跳过，不影响列表 |
| 3 | 读 Deva 旧数据（`bucket` 等废弃字段保留、`compacted` 拆分拼回） | 同文件 `test_reads_deva_legacy_fields_*`、`test_compacted_chunks_are_stitched_back` | 写回不丢未知字段 |
| 4 | Provider 抽象 + 错误归一（401/403/429/5xx/context） | `pytest app/tests/test_provider_tools.py -q` → `23 passed` | `http_error()` |
| 5 | 离线假 provider（首轮要工具、二轮总结、可注入失败） | 同上 | 不发网络、无需密钥 |
| 6 | 路径守卫：越界 / `..` / 符号链接穿越 | 同上；符号链接用例在不能建链接的平台 skip 并说明原因 | 文案 `拒绝访问：路径不在已打开的项目内` |
| 7 | `read_file`：行号 / 2000 行 / 2000 字符 / 100k 输出护栏 | 同上 | 对齐 Deva `numberedText` |
| 8 | 纵向切片端到端（ViewModel 驱动） | `pytest app/tests/test_chat_vm.py -q` → `9 passed` | 允许/拒绝/无受信根/provider 失败/无会话/异步入口/循环中止 |
| 9 | 应用入口与装配 | `pytest app/tests/test_deva_app.py -q` → `3 passed` | 服务、ViewModel、View 注册，工作区登记为受信根 |
| 10 | 全量回归（含原有 377 例） | `pytest -q` → `428 passed, 5 skipped` | 基线未破 |
| 11 | 真实 Qt offscreen 启动新入口 | `DEVA_HOME=/tmp/deva-smoke3 QT_QPA_PLATFORM=offscreen DEVA_APP_HEADLESS=1 PYTHONPATH=app/src .venv/bin/python -m deva_app` → exit `0`，`DEVA GUI OK offscreen session=main title=''` | 真实 PySide6 6.11.2 |
| 12 | 参考入口未回归 | `QT_QPA_PLATFORM=offscreen PY_UPPER_HEADLESS=1 PYTHONPATH=app/src .venv/bin/python app/src/main.py` → exit `0`，`Hello from py_upper` + `GUI OK offscreen` | 原应用仍可启动 |
| 13 | 真实 Qt 界面冒烟（输入→点发送→绑定刷新） | `QT_QPA_PLATFORM=offscreen PYTHONPATH=app/src .venv/bin/python scripts/deva_qt_smoke.py` → exit `0`，`QT SMOKE PASS` | 真控件 + 真信号 |
| 14 | 切片真机脚本 | `PYTHONPATH=app/src .venv/bin/python scripts/deva_slice.py` → exit `0`，`SLICE PASS` | 五段：允许/拒绝/落盘/重启/索引自愈 |

原始输出（逐字）：

```text
$ .venv/bin/python -m pytest -q
........................................................................ [ 66%]
........................................................................ [ 83%]
........................................................................ [ 99%]
.                                                                        [100%]
428 passed, 5 skipped in 5.56s
```

```text
$ PYTHONPATH=app/src .venv/bin/python scripts/deva_slice.py
=== 1. 允许：read_file 在受信根内 ===
status: 就绪
error: ''
tool_results: [(False, '1 行')]
transcript roles: ['user', 'assistant', 'tool', 'assistant']
assistant: 已经读取 notes.txt，内容是：     1	会议纪要：上线时间定在周五

=== 2. 拒绝：read_file 指向受信根之外 ===
tool denied: True | content == DENIED: True
assistant: 读取 /tmp/deva-slice-yahazqsz/outside-secret.txt 失败：拒绝访问：路径不在已打开的项目内

=== 3. 落盘：data/chats 下的文件 ===
  _index.json  276 bytes
  slice-allowed.json  1097 bytes
  slice-denied.json  1192 bytes
messages in slice-allowed.json: 4
content part types: ['text', 'tool_use']

=== 4. 重启：全新 Store + 全新 ViewModel 只从磁盘读回 ===
title: 看一下 notes.txt
transcript roles: ['user', 'assistant', 'tool', 'assistant']
last assistant: 已经读取 notes.txt，内容是：     1	会议纪要：上线时间定在周五

=== 5. 索引自愈：删掉 _index.json 后重建 ===
sessions after rebuild: ['slice-allowed', 'slice-denied']

SLICE PASS
exit=0
```

```text
$ DEVA_HOME=/tmp/deva-smoke3 QT_QPA_PLATFORM=offscreen DEVA_APP_HEADLESS=1 PYTHONPATH=app/src .venv/bin/python -m deva_app
This plugin does not support propagateSizeHints()
This plugin does not support raise()
DEVA GUI OK offscreen session=main title=''
exit=0
```

（前两行是 Qt offscreen 平台插件对 `resize`/`raise_` 的提示，不是错误。）

## 2. 写了但没验证

| 项 | 现状 | 为什么没验证 / 怎么验证 |
|---|---|---|
| 真实窗口（有显示服务器）下的人工交互 | 只跑了 offscreen | 容器无 X/Wayland。已用真实 Qt 控件 + 真信号覆盖装配与绑定（第 13 项），人工点击路径未走 |
| 打包后的应用（`tools/build.py`）能起新入口 | 未跑 | 打包入口仍是 `main.py`，未改；改入口是破坏性变更，待确认（见 APP-SKELETON §6.2）。另外既有的打包链路在本容器里的可行性此前未验证完成 |
| `read_file` 的图片 / Office 分支 | 未实现 | Deva 的图片缩放、docx/xlsx/pptx 提取需要额外依赖（Pillow 等），本轮只做文本分支，且工具描述里已声明只读文本 |
| 会话列表、设置页界面 | 未做 | 不在本轮范围 |

## 3. 没做 / 做不到（含原因与风险）

| 项 | 原因 | 风险 |
|---|---|---|
| 真实网络 provider（Anthropic / OpenAI 兼容） | 本轮只要求「抽象接口 + 离线假实现」，且无可用密钥 | 接入时要定 HTTP 客户端（venv 未装 httpx）与重连/空闲超时策略；`provider_gateway.py` 里的 `NotImplementedProvider` 会显式抛错，不会静默返回假数据 |
| 逐字流式刷新界面 | 需要 qasync 或工作线程接入 Qt 事件循环；本轮同步跑回合 | 长回复时界面会卡住直到回合结束；`run_turn()` 已是异步入口，后续接 qasync 不用改业务逻辑 |
| 158 条通道的批量实现 | 明确不在本轮范围 | — |
| 工具循环的权限确认（ask/approve） | P1 只做「允许或拒绝」，没有交互式授权 | 越界一律拒绝；若将来要「用户批准后放行」，需要在回合里插入界面交互点 |
| 压缩（`chat:compact`）与 `.jsonl` 拆分写出 | 只实现了**读回**旧拆分文件；`_sync_compacted` 在 P1 里恒为 None（不产生拆分） | 读旧数据没问题；新产生的会话不会拆分，长对话单文件会变大 |
| 删除 / 重命名 / 归档的界面入口 | 存储层方法已有并有测试，界面没有入口 | 只能通过代码调用；界面在下一轮 |
| 密钥存储（keyring） | 本轮无真实 provider，不需要密钥 | 接入真实 provider 时必须先解决：本容器 keyring 只有 `fail.Keyring` 后端，必须显式报「不可用」而不是落明文 |

## 4. 本轮 commit 列表（未 push）

```text
a7fba52 feat(chat): pydantic 对话模型与 Deva 兼容的会话存储
d4ac576 feat(services): provider 抽象 + 离线假实现、路径守卫与 read_file 工具
76bed55 test(services): provider 错误映射、假 provider 剧本、守卫越界与 read_file 护栏
7155647 feat(chat): ChatViewModel 串起「发送→回复→工具→落盘→重启读回」
b8311a7 feat(app): deva_app 入口与 Qt 原生聊天窗口
a269fae build: 记录本应用的运行依赖并补齐 deva_app 包标记
65ac492 feat(scripts): 纵向切片真机脚本
aafac0e docs: 应用骨架说明
ad1105d test(qt): 真实 PySide6 offscreen 界面冒烟脚本
2f8fb17 fix(build): 模板 dependencies 恢复为空，应用依赖只写 app/requirements.txt
c70b0ec docs: 构建进度台账
145b431 chore: 清理未使用的 import 与动态 import
```

上一轮（迁移计划）：`76d4009 docs: Deva→py_upper 迁移计划（158 通道契约主轴）`

## 5. 下一轮从哪继续

按优先级：

1. **会话列表 + 设置页**（`services/chat_session_store.py` 的 `list_sessions/rename_session/delete_session/set_archived`
   已可用且有测试，只差 `QListWidget` 界面与 ViewModel）：新建/切换/重命名/删除/归档；不做拖拽排序。
2. **真实 provider（先 Anthropic 一条线）**：定 HTTP 客户端 → 实现 `stream()` → 用录制的事件流做回放测试
   （不依赖网络）。同时落 `secrets_vault`：keyring 后端不可用时显式报错。
3. **流式刷新**：引入 qasync（或后台线程 + Signal），把 `run_turn()` 的事件逐条推给 ViewModel 属性。
4. **压缩写出**：把 `_sync_compacted` 按 Deva 的「前缀不变就追加、变了就换文件」实现，替换现在的恒 None。
