# 恢复点
- 218f61a：工具卡正文展示翻译、原记录字节不变测试、旧正文主题 token；50 tests passed，四张截图与 contrast.json 已落盘。
- 当前 CLI 子项：引导器8条错误（ASCII 内嵌小字典，不导入 app）、verify 检查名称、GreetingService、剩余构建提示已迁移。56 tests passed；六类命令各中英实跑在 cli-*.txt。
- verify 实跑 exit=1：现有 staging / 旧发布包不匹配当前源码；本项验证提示语言，不声称实际发布包已构建验证。
- 全仓742项分类仍在进行；不要把此恢复点当作最终完成。
- ee0f021：引导器 / 构建 / GreetingService 子项已提交。
- 742 行 review-742.csv/json 已逐条复核：298 resolved / 444 out_of_scope / 0 needs_review；out/i18n/final/audit.py 重扫当前 Python/QML，未知项失败退出。
- 全量第一遍 1399 passed / 15 failed / 9 skipped：14项中文基线/常量断言需明确语言，1项角色键误用导致“你→我”。已修角色键，旧场景显式 zh-CN、BUSY_MESSAGE 键按运行时翻译，定向回归 131 passed。
- 四组旧 QWidget 真截图与正文对比度截图完成；模型演示正文/会话标题保留用户原文，非漏翻译。等待最终全量 pytest。

- 最终全量：1414 passed, 9 skipped in 350.50s (0:05:50)，exit=0；本轮四项收口和零未解释残留已验证，等待最终证据提交与 push 核对。
