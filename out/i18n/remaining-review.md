# 收口清单（本次恢复执行）

- [x] 恢复既有进度，不重做已完成的翻译生成。
- [x] 修改前文件:行号 → 原文 → 键对账：close/mapping.md、mapping.json；具体已迁移项见 migrated.json、extra-migrated.json。
- [x] 旧 QWidget 设置、主窗、对话框和 ViewModel 主要文案迁移；中英文真实启动并截图。
- [x] 工具卡角色、成功失败状态、清单展开收起取消和已知摘要接入翻译；原始工具记录不改写。
- [x] CLI --lang、AI_UPPER_LANG、配置 locale、系统 locale 统一选择；每语言 7 条命令实跑。
- [x] 中英资源键集合一致；当前 2098 键/语言，缺键 0；插值缺参 0。
- [ ] Python/QML 全仓用户文案逐条复核与零未解释残留：尚未完成。close/scan.json 中 needs_review 仍非零。
- [ ] 旧工具卡正文的应用生成说明全部本地化：尚未完成；原始记录应保留，展示边界需继续完善。
- [ ] 深色旧富文本正文对比度验收：未通过，固定浅色样式仍需修复。
- [ ] bootstrap egg_loader 与剩余构建校验名称全部迁移：尚未完成。
- [x] 全量 pytest：1409 passed、9 skipped、0 failed，退出码 0；原始日志 close/pytest-final.txt。

本文件的勾选只代表列出的结果，不把资源缺键为零当成全仓迁移完成。详细剩余项在 close/STATUS.md。
