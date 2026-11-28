# 合并冲突
上游GitWidget.tsx:247–265：冲突warning toast带中止快捷操作。现在真实diff --diff-filter=U读取冲突文件，仅有冲突文件才返回conflict（不再把所有merge失败误判成冲突）。GitMenu右上非模态提示列文件，按钮直接merge --abort。
merge-dark/light.json及conflict.png：真实冲突文件a；中止后status空，MERGE_HEAD exit128、fatal: Needed a single revision。功能路径完成。视觉仍有差异：提示不是完整通用Toast复刻，缺关闭按钮/自动消失策略，边框使用整圈warning而非原版3px左边框；不得称逐像素同构。
