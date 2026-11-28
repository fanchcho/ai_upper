# 身份作用域
原版本地定制GitIdentityForm.tsx:52–56为local/global select；上游main没有该恢复表单，这一区别继续保留。GitMenu以ComboBox替换CheckBox，32px输入高度、主题背景/边框，选项当前仓库/全局。
真实场景先删除fixture身份并启用user.useConfigOnly；提交前字段不可见，真实commit失败才显示。键盘选择全局，currentIndex=1；保存后git config --global读回Scope User / scope@example.invalid；再提交成功，subject=identity verified。GIT_CONFIG_GLOBAL显式指/tmp隔离文件，未写真实全局配置。暗亮missing/scope.png与JSON可复核。
