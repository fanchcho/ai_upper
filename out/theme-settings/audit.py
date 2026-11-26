from pathlib import Path
import re
root=Path(__file__).resolve().parents[2];out=root/'out/theme-settings'
lines=['# 设置组件审计','', '以下行号指修复前快照（同原始源文件行号）。透明色是有意透出父背景。所有设置页共用 SettingsModal 背景/侧栏/遮罩；正文 QTextDocument 不在本次改动范围。','']
for f in ['SettingsModal','PluginSettingsPane']:
 lines+=['## '+f,'','```text']
 for n,line in enumerate((out/(f+'.before.qml')).read_text().splitlines(),1):
  if re.search(r'color:|opacity:|TextField\s*\{|TextArea\s*\{|ComboBox\s*\{|Button\s*\{|CheckBox\s*\{|ScrollView\s*\{',line):lines.append(f'app/src/qml/{f}.qml:{n}: {line.strip()}')
 lines+=['```','']
lines+=['|页|背景/文字|输入|按钮/开关|分隔/空状态/滚动|','|---|---|---|---|---|',
'|General|bgPanel/fg/fgMuted|无|Theme 分段选项|border；无滚动|',
'|Models（含 provider/advanced）|bgPanel/fg；小字 fgSubtle 不达标|高级头输入已有 Theme；占位符 fgSubtle|自定义网络 Button 漏绑；开关白色硬编码；确认危险白字|border；空状态 fgSubtle；无滚动条|',
'|Extensions|bgPanel/fg；注释 fgSubtle|无|开关白色硬编码，内置禁用 opacity .55|border；空状态 fgSubtle；无滚动条|',
'|About|bgPanel/fg；版本 fgSubtle|无|检查更新 Theme；checking opacity .45；状态字 success/danger|无输入/分隔/滚动条|',
'|Custom model|标题 fg、说明 fgMuted|所有 TextField 漏绑|Save/Clear Button 漏绑|无分隔/滚动；状态 fgMuted|',
'|MCP|标题 fg、状态 fgMuted|ComboBox/TextField 漏绑|CheckBox/三个 Button 全漏绑|无分隔/滚动；空 ComboBox 无提示|',
'|Personas|标题 fg|ComboBox/TextField/TextArea 漏绑|Save Button 漏绑|ScrollView 滚动条为平台默认|','',
'修复：新增设置专用 Basic 控件；原版 token 绑定背景、文字、边框、焦点、选区、按钮态、复选框、下拉弹层与滚动条。小字改 fgMuted；危险按钮用 danger 边框和 fg 正文。详见 git diff。']
(out/'AUDIT.md').write_text('\n'.join(lines)+'\n')
