# 上游版本台阶（本轮重新核实）

用户客户端：未知。原版本地副本：0.1.17 / 8a0746a03674614f7ccf10e78d422914ba31bc9c。上游main最新：0.1.17 / 013c5d7eb4cd0907e02bc8717219a0bef42fb1fc。移植About声明基线：0.1.16；Python项目版本0.17.33独立，不用于算deva版本差。上游比声明基线高一个patch；本地与上游包版本相同、本地包含上游且多74个提交。用户实际客户端与上述谁新谁旧未知。

本地deva由其他执行更新到了8a0746a，本执行没有修改它。上一轮25c2935仅是历史时点；不能继续当现状。原目录只执行了log/remote/merge-base/rev-list等只读命令，没有fetch/checkout。

```text
$ git -C /home/agent/shared_workspace/deva log -1 --format='%H %cs %s'
8a0746a03674614f7ccf10e78d422914ba31bc9c 2026-11-28 style(deva-agent): 统一设置页基线并调整技能分栏 / unify settings baseline and align skill split layout
$ read apps/desktop/package.json version
0.1.17
$ git ls-remote https://github.com/sqfcyily/deva.git refs/heads/main refs/heads/develop
013c5d7eb4cd0907e02bc8717219a0bef42fb1fc refs/heads/main
$ git ls-remote git@github.com:fanchcho/deva.git refs/heads/main refs/heads/develop
013c5d7eb4cd0907e02bc8717219a0bef42fb1fc refs/heads/main
$ git -C /home/agent/shared_workspace/deva merge-base --is-ancestor 013c5d7eb4cd0907e02bc8717219a0bef42fb1fc HEAD
(no output; exit 0)
$ git -C /home/agent/shared_workspace/deva rev-list --count 013c5d7eb4cd0907e02bc8717219a0bef42fb1fc..HEAD
74
```

两个remote均没有返回develop，不虚构该分支。即使本地不落后，仍按用户要求在/tmp浅克隆并fetch上游以避免混入本地定制；命令原文clone.log、upstream.json。clone/fetch退出0，最新package.json version=0.1.17。版本源是apps/desktop/package.json；未发现能证明桌面另有更高发布版本的证据。这里“最新”指本轮查询main，不推断其它分支/未发布客户端。

移植依据：app/src/mvvm/services/provider_registry.py:35-36 APP_VERSION=0.1.16；qml_shell.py:456-458读取；qml/SettingsModal.qml的appVersion显示。app/pyproject.toml:19 version=0.17.33。不将单页改动伪装成全站升级。

仓库初始HEAD=origin/develop=259577942cd764a514c15f44b7317858b84cc186；status空。log -6：2595779、4db9aeb、4d37256、dd3f91e、515b587、e8fdc2c。未回退或重做这些提交。此前execution中断说法不用于覆盖实际Git历史。
