# 工程迁至 pc/ai_upper

实体目录 /home/agent/shared_workspace/pc/ai_upper。旧 ai_upper 与 /home/agent/shared_workspace/py_upper 均软链到该实体；保留前者是因为宿主workspaceRoot仍指旧路径，删除会使会话cwd失效。迁前/home/agent/shared_workspace/py_upper实际上不存在，不能照旧回执写成存在；本次已重建。

迁前HEAD e8fdc2cad57b073e46e5d16f99d6645fdbce8173，status为空，无未提交或未推送的本地提交（HTTPS回读同SHA）；因此不需要归档未提交改动。/proc文件描述符检查未发现工作树文件写入者。实体与父目录设备号同为2050，按用户要求cd /后同一条命令执行mv及两个ln -sfn，无复制删除。迁后HEAD/status保持一致、4669个跟踪文件、.git 80604192字节与迁前完全一致；du约9.4G。fsck --full退出0，仅已有dangling对象；count-objects garbage=0。

SSH远端查询失败：私钥/home/agent/.ssh/fanchcho不存在，Host key verification failed；默认ssh同样Permission denied(publickey)。HTTPS只读回读成功，push无Username凭据，不能声称已推送。原文remote-*.log及后续push日志保留。

引用处理：references.json列出迁前跟踪文本命中404文件4713处。audit-tools/gen_migration_plan.py当前生成目标1处、docs/MIGRATION-PLAN.md当前目标1处改新路径；README追加迁址说明。401个历史文件4710处保留当时事实，另1处app/tests/test_app_home.py为明确测试旧入口的兼容常量，不改断言或历史输入。运行数据目录、AI_UPPER_HOME、~/.ai_upper、deva参考路径未替换。

本地venv/bin 41文件42处入口/shebang/激活路径更新，未改依赖版本；备份.tmp/migration/venv-entrypoints-before.tar与venv-backup.sha256。pyvenv.cfg的创建命令是历史事实保留。build/.tmp的构建缓存、core、旧日志不批量重写；旧路径仍由软链兼容，重构建可使用新cwd。

全盘grep首次原命令可能扫描到自己的输出，停止后排除migration/pc-migration两个证据目录重跑，输出.tmp/migration/all-references.log与grep-final-errors.log，避免递归自引用；跟踪文件的独立完整分类在references.json。

迁后新入口最小3 passed in 6.55s；旧入口最小3 passed in 5.85s。全量结果另见full.log/full.exit，均使用/tmp独立home、offscreen/software与隔离wm库；无Qt预载。

迁后全量实际结果：1486 passed / 9 skipped / 0 failed，563.18秒，exit0。
