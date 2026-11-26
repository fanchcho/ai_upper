# 最终裁决与收尾

用户明确裁决：停止继续追冷路径和空闲预热，不再重试延后挂接、表格批量事务或几何前置。本轮仅归档、验证和推送，不能称为性能已解决。

- **热路径已达标**：历史e1fbf80验收约21.6 / 23.5 / 14.6 ms（完整帧中位/P95/最长GUI），保留现有实现；这些是历史结果，不是本轮重新测量。
- **冷路径未达标**：上轮回退后约126 / 138 / 57 ms，套用60 / 80 / 16.7阈值约超66 / 58 / 40 ms；依用户决定不再继续追。
- **空闲预热否决**：GUI提交不可抢占，未进入产品代码。
- **N从4降到1仍无效**：只能降低提交发生频率，无法缩短一次22–25 ms不可抢占提交，也不能让等待中的输入立即执行。

`git status --porcelain`只有未跟踪审计目录；`git diff --exit-code cf960b8 -- app/src app/tests`无输出、exit0。完整对账见closeout-checks.json。无需回退任何源码。

## 有效三组阈值对比

|模式|第1组最长GUI ms|第2组|第3组|相对16.7 ms门槛|
|---|---:|---:|---:|---|
|无预热|0.258|0.505|0.248|全部低于门槛|
|空闲预热|29.433|28.635|28.936|分别超12.733/11.935/12.236 ms|
|预热期间点击|28.681|31.486|29.459|分别超11.981/14.786/12.759 ms|

片段提交22–25 ms、表格阶段约26 ms；点击等待三组最大53.334 / 59.642 / 54.996 ms。下一阶段延后10ms的取消边界试验成功取消3次后续阶段，但最长GUI仍28.026 ms、输入等待最高26.202 ms，仍否决。不能把定时器等待当成真实硬件输入到屏幕的精确延迟。

## 归档与清理

75个临时文件完整复制到本审计目录、逐个SHA-256验证后删除`.tmp/idle-prefetch`；archive-manifest.json记录原位置、归档位置、长度及哈希。有效三组以control2/idle2/input2及exits.json为准；首轮错误/非零轮次仍留作失败记录，不计通过。上轮pytest在61%左右中断，没有最终输出与退出码，归档为pytest-interrupted.log，**未验证，不计通过**。源目录和测试目录零差异，所以本轮按用户决定只执行相关子集。

本轮新临时目录`.tmp/idle-closeout`仅保留验证运行与推送收据，明确登记，不含运行时探针。/tmp应用数据未触及真实用户目录；不操作deva或依赖pin。

---

以下保留上一轮探针设计与原始结论；尚未实现部分不再推进。

# 空闲预热准入试验：否决，产品保持原状

起点cf960b8，git status --short无输出。没有修改app/src或app/tests。本轮没有完成可交付的idle prefetch，也没有把探针当作实现。

## 设计与准入

拟选最近4项（现有32项容量的1/8，避免预热挤出多数用户已打开会话），连续空闲1秒，单worker、一次一会话、GUI目标片预算8ms。拟共享现有32项/128MiB估算LRU，不增加第二缓存；完整预算集成尚未实现。先验证不可省略的显示文档提交能否过片预算，失败就不接入LRU。

隔离探针用同一24落盘会话/每条30轮正文，在首屏之后构建4个隐藏TextEdit。后台prepare_document返回fragment，GUI分别执行片段提交/高亮和overlay，沿用正文渲染函数、不批处理表格、不延后接入以优化冷总帧。QTimer轮转、输入eventFilter更新epoch，后续阶段核对generation。首屏与当前活动ID不改变。没有预先打开待测会话。

`body.py:214-221`的insertFragment/endEditBlock包含同步高亮与布局；`viewport.py:161-185`的几何查询/setFormat仍同步发生。输入eventFilter只能在这些调用返回后获得事件，generation不能抢占正在执行的Qt调用。把N从4降到1只能减少频率，不会缩短单片。

## 实测

全部下列有效轮次exit0，exits.json保存9个退出码。表中“输入等待”是1ms定时器到期到派发的额外等待，点击通过QTest注入；不是硬件OS输入延迟。GUI最长事件由notify计时，点击函数耗时单独保存在JSON，不能用后者掩盖排队。

|模式|组|最长GUI事件ms|输入/定时器最大等待ms|完成数|RSS峰值KiB|首屏耗时ms|
|---|---:|---:|---:|---:|---:|---:|
|control2|1|0.258|0.000|0|175032|4771.254|
|control2|2|0.505|0.000|0|177064|4769.593|
|control2|3|0.248|0.000|0|176940|4795.851|
|idle2|1|29.433|54.506|4|196960|4760.114|
|idle2|2|28.635|53.311|4|195244|4768.021|
|idle2|3|28.936|54.511|4|197236|4764.309|
|input2|1|28.681|53.334|3|190260|4772.386|
|input2|2|31.486|59.642|3|192476|4761.372|
|input2|3|29.459|54.996|3|192484|4763.031|

无预热control2最长GUI不足1ms；idle2为28.6~29.4ms；input2为28.7~31.5ms，全部超16.7。下一阶段0ms定时器会先于已经到期输入回调执行，因此epoch尚未更新、取消数为0，输入等待最高59.642ms。此版本否决。

补测cancel-probe将后续阶段延后10ms：3次后续工作均取消，但片段提交仍21.683~25.530ms，最长GUI28.026ms，输入额外等待最高26.202ms，仍失败。没有通过隐藏点击排队来宣称取消及时。没有将已否决的分段渲染引入运行时。

首屏数值是fixture创建、落盘、窗口初始化到grabWindow的代理量（约数秒），不是纯应用启动首屏可交互指标；预热在此抓帧后才创建。真正首屏可交互差值**未验证**：产品未接入且夹具启动计时含数据生成，不能拿此列当启动零代价证明。

9轮当前可见帧前后RGB差异均为None、活动ID未改变。但隐藏预热正文没有接入LRU并实际打开，因此**预热打开的正文像素/哈希/标题/活动ID一致性未验证**，不冒充最终帧验收。

## 未完成与回退

- 真冷72次及预热后72次实际打开：未验证，GUI准入已失败，未形成可用的预热LRU项。未用历史数据充当本轮数据。
- 命中率：产品未启用预热；探针没有写入LRU，不能宣称预热命中。
- 96会话压力及RSS稳定：未验证，预热集成被否决；表中仅4个隐藏文档峰值，不是有界长期内存证明。
- 热路径21.60/23.55/14.60门槛：本轮未重新测量；产品源码完全没动，不代表实测保证。
- N/8ms片/128MiB完整预算及即时取消：没有完成；当前Qt提交本身超预算。

仅提交审计脚本、日志、截图，不保留产品半成品。冷路径旧实现和热LRU原样保留。不改pin、不引入WebEngine、不改deva、不访问真实用户数据。

## 命令与失败证据

`python .tmp/idle-prefetch/run2.py`依次执行control2/idle2/input2各三组，不与pytest并发。子进程AI_UPPER_HOME=/tmp/ai-upper-idle-{mode}-{group}，LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu，PYTHONDONTWRITEBYTECODE=1，脚本设置offscreen/software。`PROBE_INPUT=1`仅用于input2。`python .tmp/idle-prefetch/finish.py`串行执行取消边界和全量pytest。

首轮probe存在错误消息参数及隐藏item生命周期异常，prefetch-1/2退出1；首轮其余运行期间探针发生修正，也全部排除。日志保留但不作有效测量。有效三组仅control2/idle2/input2；cancel为独立否决边界证据。没有将非零退出算通过。

## 本轮收尾验证（有效）

```bash
AI_UPPER_HOME=/tmp/ai-upper-idle-closeout QT_QPA_PLATFORM=offscreen \
LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu" PYTHONDONTWRITEBYTECODE=1 \
.venv/bin/python -m pytest app/tests/test_display_cache.py app/tests/test_qml_shell.py \
 app/tests/test_markdown_body.py app/tests/test_markdown_document.py \
 app/tests/test_markdown_highlight.py -q --basetemp=/tmp/ai-upper-idle-closeout-base
```

真实输出：`158 passed in 22.27s`，0 failed、0 skipped，退出码0；完整日志pytest-closeout.log。没有将全仓库9个条件skip算作执行通过，本轮按最新指令没有重跑全量。`git diff --check`无输出，源码与测试相对cf960b8零差异。

本轮仅提交docs/audit/session-switch/idle-prefetch/审计文件。提交后普通推送develop，运行收据保留于`.tmp/idle-closeout/PUSH-RECEIPT.md`；包含推送前远端、最终HEAD、真实输出与每步退出码。收据含最终提交hash，不递归提交自身。
