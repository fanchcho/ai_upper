# 第0步原始对账

本轮开始实际输出：
```text
$ git log --oneline -8
7c20b32 feat: add git remote management controls to the panel
942d232 docs: record F41/F56/F78 conclusions and updated parity counts
0d057b9 test: verify telegram bot protocol against a local endpoint
d388296 feat: add member background task list with open and cancel
2f44832 feat: implement persistent role memory in persona profile
49d2c4f feat: complete git panel diff discard merge branches and remote operations
4928910 docs: record final full regression evidence
98b5f69 test: provide QtQml in the isolated module-import fixture
$ git status --porcelain
 M scripts/parity/feature_parity_evidence.py
$ git rev-parse HEAD
7c20b324f3a22c59b26a3427bca5c316100c94db
$ git ls-remote origin refs/heads/develop
7c20b324f3a22c59b26a3427bca5c316100c94db	refs/heads/develop
```

已核对09de966、9e5c29d、a7ee565、649f93f均为origin/develop祖先，不回退、不重复验收。

开场残留 scripts/parity/feature_parity_evidence.py 是其他执行增加的 background 证据函数，只保留，未由本执行提交。原始差分 residual.diff。98b5f69 改测试 fixture 是本轮之前的外部提交，本轮没有修改既有测试文件或断言，不将它算成本轮修复。

执行中再次出现并发写入：
- 41cbfebefc03cc58413cb09ee95ba12a6e5dcac2：外部执行提交/推送，包含本执行仍在验证的成员工具、目录与列表修改，以及原始full.log。没有回退，不冒领其Git操作。
- 00fa741fe56bd49a938ac694b7ab73b14dd42fc3：外部执行提交/推送，包含本执行仍在验证的决策配置、执行逻辑和渠道回执修改。没有回退，不冒领其Git操作。
- docs/audit/feature-parity-gap.md/.json 与 docs/audit/evidence/* 被外部重写；本执行未重做已验收89项盘点，也不将这些修改纳入验收。原始差分 external-residual.diff。

最终回归使用 git archive bd9b463 的独立源码副本，隔离持续变动的工作树。与本轮最终生产源码核对，后续仅证据文档变化。应用 home/basetemp 指 /tmp，辅助副本在仓库 .tmp，不碰 ~/.ai_upper。
