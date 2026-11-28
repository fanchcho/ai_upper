# 远程分支删除
上游GitWidget.tsx:326–338：确认后push remote --delete branch。移植git_service.py:165起已有真实push实现；本轮修复失败提示不可见：GitMenu提示框增加gitPromptError，显示原始Git错误。
remote-dark/light.json记录真实/tmp bare remote的ls-remote --heads前后差异：remote-delete从存在到空。failure截图为remote改成缺失目录后真实拒绝，含“does not appear to be a git repository”，控件visible实测true。不冒称公网服务成功。
