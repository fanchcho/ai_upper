# AvatarStack余量与角色键盘导航

## 原版依据

只读原版redesign/shell-common.tsx:175–216：size=20、max=3，人数>3时shown取前2人，more=总人数−2，第3人的头像上覆余量。因此5人应显示两张普通头像+第三张遮罩头像「+3」，不是「+2」。redesign/redesign.css:5214–5258：间距−6px，遮罩黑55%，白字9.5px/600，≥10缩为8px，字距−.02em。

components/Select.tsx:126–147、:195–223：打开定位首个选中项，无选中用第0项；方向键边界钳制，不循环；Home/End跳首尾；Enter/Space选择，具体角色多选保持打开，所有角色closeOnPick关闭；Tab关闭。

## 改前改后

- 原列表和详情均Repeater展开全部角色；现在共用AvatarStack.qml，≤3全部显示，>3只渲染3个槽位，最后一位显示+N。5人宽度20×3−6×2=48px，原5人展开宽76px。
- 余量底层仍为真实第3个角色。personaVeil从已生成Humation SVG读取同一shape路径，绘制黑55%覆盖，因此云形/其他spec不被硬编码成圆；用户图片也使用同seed/spec的遮罩形状，与原版规则一致。
- 原菜单无活动行键处理；新增触发器按键打开、Popup内容焦点与活动行按键处理，Enter/Space经原保存桥写配置。保留鼠标选择、所有角色、check、高亮及原有菜单外观。
- SettingsModal.qml只替换列表头像Row为AvatarStack；导航入口、路由和服务不改。原版typeahead不在本轮指定按键验收范围，本次没有声称已实现按名称快速定位。

## 真实5角色fixture与键盘事件

fixture五份persona文件：reviewer/writer/tester/designer/analyst，skill alpha.roles真实配置为这五项；此外原内置general/xiaomajiang使菜单具体角色共7项，加所有角色项共8项。运行脚本scripts/parity/extensions_roles_evidence.py从真实SKILL.md/personas/config.json读取，不硬编码前端展示列表。

暗亮都实际QTest.keyClick，日志：
```
Home activeRow 0 opened True
Down activeRow 1 opened True
Up activeRow 0 opened True
End activeRow 7 opened True
Home activeRow 0 opened True
Down activeRow 1 opened True
Enter activeRow 1 opened True
ENTER persisted [reviewer,writer,tester,designer,analyst] -> [reviewer,writer,tester,designer,analyst,general]
Home activeRow 0 opened True
Enter activeRow 0 opened False
ALL PERSONAS Enter persisted null and closed
```

首次探针没有激活窗口且findChild拿到未打开实例导致assert失败；修正为requestActivate+真实trigger focus并取opened Popup后通过。失败dark.log/light.log保留；最终dark-final.log/light-final.log为有效结果。未改测试来规避。

截图均真实Qt1280×820：out/extensions-roles/{dark,light}-five-role-stack.png、list.png、keyboard-home.png、keyboard-end.png、keyboard-selected.png。5角色余量Text实测13.40625×11px，详情文本位置x509/y339.5；显示「+3」。原版9.5px对应QML7.125pt，尺寸20px、间距−6px；≥10字体8px对应6pt。

## 验证命令

```sh
AI_UPPER_HOME=/tmp/ai-upper-roles-dark2 \
XDG_DATA_HOME=$PWD/.tmp/extensions-roles/data XDG_CACHE_HOME=$PWD/.tmp/extensions-roles/cache \
TMPDIR=$PWD/.tmp/extensions-roles LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
.venv/bin/python scripts/parity/extensions_roles_evidence.py dark
# light同脚本、独立/tmp/ai-upper-roles-light2

AI_UPPER_HOME=/tmp/ai-upper-roles-tests \
LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
.venv/bin/python -m pytest app/tests -q --basetemp=/tmp/ai-upper-roles-tests/tests
```

上一轮圆底/外环/阴影/正文的取整残差保持原样，未动token。原版成功保存密钥态仍未验证：无OS凭据服务，不能伪造成功。仅这两项功能按本轮范围验证，不把截图称为整页像素归零。

最终全量回归：1429 passed, 9 skipped in 366.38s (0:06:06)，0 failed；完整pytest.log。git diff --check通过，旧测试无改动。正常推送origin/develop后远端回读与本地HEAD保存git-verification.json。
