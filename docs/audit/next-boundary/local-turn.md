# 中文消息回合：本地 HTTP fixture 闭环

scripts/parity/full_app_local_turn.py执行生产qml_shell.run(False)，真实Qt6.8.2/fcitx键鼠输入中文。local_model_fixture.py启动127.0.0.1随机端口，按OpenAI chat completions SSE返回“本地 fixture 收到你好”；不替换ChatHost或transport，不是真实外部模型。

暗亮均REAL_HTTP_MESSAGE_READBACK True。http-request-*.json记录真实HTTP路径与消息；dark/light-readback.json是新建ChatSessionStore重开后的user你好、assistant本地fixture正文；dark/light-session.json归档实际会话文件。D-Bus记录和完整应用preedit/commit截图一并保存。默认QtABI未完成，因此本轮使用已验证系统Qt组合；没有重做旧输入验收，此处新增的是HTTP与消息持久化链路。

复现：bash scripts/parity/local_turn_run.sh <唯一后缀>，仍要求此前隔离系统Qt依赖。fixture只监听loopback，进程结束停止。外部模型成功态仍未验证。
