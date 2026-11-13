# Deva 应用骨架（第一阶段）

> 目标工程：`/home/agent/shared_workspace/py_upper`
> 参考工程（只读）：`/home/agent/shared_workspace/deva`，commit `109937f85b5d1b0c0a95c8875390e07ddccdf544`
> 状态：骨架可运行；业务只实现了一条纵向切片（见 `docs/BUILD-PROGRESS.md`）

## 1. 结论先行

- **包名**：`deva_app`，位于 `app/src/deva_app/`。
- **入口**：`python -m deva_app`（设置 `PYTHONPATH=app/src`），见 §3。
- **没有第二套 MVVM**：ViewModel 基类、可观察属性、命令、绑定、容器、Qt 引导全部复用
  `app/src/mvvm/`（`core/`、`views/base_view.py`、`mvvm_application.py`、`mvvm_bootstrap.py`）。
  新工程只往里加**具体类**，不复制框架代码。
- **装配处唯二**：参考实现仍由 `app/src/application.py::PyUpperApplication` 装配；
  新应用由 `app/src/deva_app/__main__.py::DevaApplication` 装配。两者都继承
  `MVVMQtApplication`，互不影响，原有 377 个测试保持全绿。

## 2. 文件树与职责

```
app/src/
├── deva_app/
│   ├── __init__.py            包标记 + 入口说明
│   └── __main__.py            DevaApplication（装配处）+ run()/main()；三个环境变量
├── mvvm/                      框架层（既有，不改）
│   ├── core/                  BaseViewModel / ObservableProperty / RelayCommand
│   ├── mvvm_application.py    ServiceLocator + ViewModel/View 注册表 + 生命周期
│   ├── mvvm_bootstrap.py      MVVMQtApplication：QApplication、prepare/run/quit
│   └── views/base_view.py     ViewBase / MVVMBinding / CommandBinding
├── mvvm/models/
│   └── chat_models.py         新增：pydantic 对话模型（与 Deva 落盘 JSON 逐字段兼容）
├── mvvm/services/
│   ├── chat_session_store.py  新增：一对话一文件 + _index.json + compacted .jsonl
│   ├── provider_gateway.py    新增：Provider 抽象、归一化 StreamEvent、NormalizedError
│   ├── fake_provider.py       新增：离线假 provider（确定性剧本，不发网络）
│   ├── workspace_guard.py     新增：受信根 + realpath 越界拒绝
│   └── tool_runtime.py        新增：工具声明/执行入口 + read_file
├── mvvm/view_models/
│   └── chat_vm.py             新增：ChatViewModel（发送→流→工具→落盘的回合逻辑）
├── mvvm/views/
│   └── chat_window.py         新增：ChatWindow（Qt 原生，全部走 ViewBase 绑定）
app/tests/
├── test_chat_session_store.py 16 例：存储、索引自愈、旧字段、拆分文件
├── test_provider_tools.py     23 例：错误映射、假 provider、守卫、read_file 护栏
├── test_chat_vm.py             9 例：端到端（允许/拒绝/失败/循环/重启读回）
└── test_deva_app.py            3 例：装配、入口、窗口绑定
app/requirements.txt           本应用运行依赖（PySide6 6.11.2 + pydantic 2.14.3）
scripts/deva_slice.py          纵向切片真机脚本（不依赖 pytest）
```

### 每个文件的职责边界

| 文件 | 做什么 | 不做什么 |
|---|---|---|
| `deva_app/__main__.py` | 组织对象图、读环境变量、启动/退出 Qt | 不写业务判断；没有 Qt 时仍可被 import |
| `models/chat_models.py` | 落盘结构定义、类型校验、未知字段保留 | 不读写文件、不调 provider |
| `services/chat_session_store.py` | 文件读写、索引维护与自愈、标题派生 | 不 import Qt、不认识 ViewModel |
| `services/provider_gateway.py` | 归一化类型与接口；HTTP 错误映射 | 不做网络请求（真实适配器尚未实现） |
| `services/fake_provider.py` | 确定性回放，跑通链路 | 不冒充真实适配器（未实现的会显式抛错） |
| `services/workspace_guard.py` | 受信根、真实路径、越界判定 | 不碰全局状态（根是实例态） |
| `services/tool_runtime.py` | 工具注册、参数解析、执行、结果整形 | 不决定「该不该调工具」（那是模型/VM 的事） |
| `view_models/chat_vm.py` | 回合编排、属性通知、错误转界面文案 | 不 import Qt、不碰窗口 |
| `views/chat_window.py` | 建控件、绑属性与命令 | 不做业务判断、不直接读写存储 |

## 3. 入口与运行方式

```bash
# 依赖（一次性）
.venv/bin/python -m pip install -r app/requirements.txt

# 真实窗口
PYTHONPATH=app/src DEVA_HOME=/tmp/deva-home DEVA_APP_WORKSPACE=/path/to/workspace \
  .venv/bin/python -m deva_app

# 无显示环境（CI / 验收）：offscreen 装配一次再退出
PYTHONPATH=app/src DEVA_HOME=/tmp/deva-home \
  QT_QPA_PLATFORM=offscreen DEVA_APP_HEADLESS=1 .venv/bin/python -m deva_app
```

环境变量：

| 变量 | 缺省 | 作用 |
|---|---|---|
| `DEVA_HOME` | `~/.deva` | 数据目录；与 Deva 桌面端同口径，两边可互相读写 |
| `DEVA_APP_WORKSPACE` | 空 | 启动时登记为**受信根**；不设则没有受信根，工具一律拒绝 |
| `DEVA_APP_HEADLESS` | 空 | `1` = offscreen 装配一次就退出（并打印 `DEVA GUI OK`） |

`python -m main`（参考实现）不受影响，仍打开原来的示例窗口。

## 4. 数据流（一条消息的完整路径）

```
ChatWindow(输入框)
  → MVVMBinding.update_viewmodel_from_ui()      input_text
  → CommandBinding → ChatViewModel.send_command
      → asyncio.run(ChatViewModel.run_turn(text))
          → ChatSessionStore.append_message(user)       [磁盘]
          → Provider.stream(GenerateRequest)            [假 provider]
          → ToolRuntime.execute("read_file", {...})
              → WorkspaceGuard.assert_inside(path)      [越界即 DENIED]
          → ChatSessionStore.append_message(tool_result)[磁盘]
          → Provider.stream(...) 第二轮                 [总结]
          → ChatSessionStore.append_message(assistant)  [磁盘]
  → PropertyChangedEvent → 绑定刷新界面
```

## 5. 与 Deva 的已知差异（刻意为之）

| 点 | Deva | 本工程 | 原因 |
|---|---|---|---|
| 工具路径限制 | agent 文件工具**无限制**（2026-10-09 起） | 必须过 `WorkspaceGuard` | 新工程的安全底线，迁移计划已定 |
| 单条对话落盘失败 | 静默（只留内存态） | 抛异常，由 ViewModel 转成界面错误 | 用户不该以为存下了 |
| 回合执行 | 主进程异步流式 + 逐字推送 | 回合是异步的（`run_turn`），但按钮入口用 `asyncio.run` 同步跑完才刷新 | 逐字刷新需要 qasync/工作线程，P1 不引入；不假装做到 |
| 真实 provider | Anthropic / OpenAI 兼容 | 只有离线假实现；真实适配器显式 `NotImplementedError` | 没有密钥也跑通链路；不留假数据 |

## 6. 待确认

1. **真实 provider 的接入时机**：P1 未做网络适配器。需要确认是否引入 `httpx`（当前 venv 未装）
   还是走标准库 `http.client`；这会决定 `provider_gateway.py` 的依赖与重连实现。
2. **打包入口**：`app/pyproject.toml` 的 `[tool.py_upper].entry` 仍是 `main.py`。
   要把新应用作为发行入口，需要把入口改为 `deva_app/__main__.py` 或新增一个启动脚本——
   这会改变参考实现的打包行为，属于破坏性变更，未擅自执行。
3. **会话列表/设置页**：本轮只做单会话聊天窗口，左侧列表与设置页未做（见 `BUILD-PROGRESS.md`）。
