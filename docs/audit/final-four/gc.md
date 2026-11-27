# 独立启动 GC

原版 main/index.ts:351 启动调用 sweepCheckpoints；services/checkpoints.ts:56 MAX_TURNS=100，:58 RETAIN_MS=30天，:332 sweepCheckpoints。移植沿用上轮 inline journal 保留元信息/释放内容规则，在 ChatHost 构造时独立扫描，不需要下一次工具写入。

scripts/parity/startup_gc_evidence.py 向全新 /tmp 应用 home 写入 105 轮近期快照和一条 31 天旧快照，然后启动真实 app/src/main.py 子进程。没有直接调用 GC。读回 106 条元信息全部保留，7 条 payload 被释放（100轮上限先释放6，过期项再释放1）；原始日志 gc.log。

单个坏 journal 打印 REWIND GC FAILED 后继续，符号链接 journal 跳过。原版 blob 目录布局与本项目 inline journal 不同，本轮不迁移既有已验收存储格式。
