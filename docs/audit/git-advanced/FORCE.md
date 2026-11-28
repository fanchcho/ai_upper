# 未合并分支二次确认
原版GitWidget.tsx:284–309：先-d，unmerged时按count再次确认，允许才-D。git_service.delete_branch现在用HEAD..name真实rev-list计数；GitMenu的forceDelete状态保留原分支名和计数，取消不调用-D。
暗亮真实鼠标：创建独有1次提交的unmerged分支，首次确认进入二次确认，正文含“1 个提交”；取消后独立git branch读回unmerged；再次操作确认后读回空。force-dark/light.json与confirm.png、日志可复核。真实Git，本地fixture，无模型替身。
