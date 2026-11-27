import json
from pathlib import Path
j=json.load(open('docs/audit/feature-parity-gap.json'))
groups={
'app/tests/test_qml_window_controls.py':['F04','F05'],
'app/tests/test_qml_links.py':['F07'],
'app/tests/test_qml_edit_menu.py':['F09'],
'app/tests/test_qml_sidebar_collapse.py':['F10','F27b'],
'app/tests/test_qml_shell.py':['F12','F16','F29','F57'],
'app/tests/test_qml_session_switch.py':['F17'],
'app/tests/test_qml_context_menu.py':['F18','F19','F20','F21','F24','F28'],
'out/parity-close/filter.json':['F22','F23'],
'out/final-port/unread-attention.json':['F25'],
'scripts/parity/draft_evidence.py':['F26'],
'app/tests/test_qml_plugin_settings.py':['F31'],
'app/tests/test_qml_stop_generation.py':['F37'],
'out/final-port/compact-ui.json':['F39'],
'app/tests/test_qml_context_ring.py':['F43'],
'app/tests/test_qml_model_picker.py':['F44'],
'app/tests/test_qml_chat_files_ui.py':['F45','F48','F49','F77'],
'app/tests/test_qml_attachments_drop.py':['F46'],
'out/parity-close/roster.json':['F51'],
'out/final-port/tasks-ui.json':['F59'],
'app/tests/test_qml_settings_theme.py':['F65'],
'app/tests/test_qml_settings_provider.py':['F66','F68'],
'app/tests/test_qml_extension_details.py':['F69','F71','F72'],
'app/tests/test_qml_settings_overlay.py':['F73','F74'],
'out/final-port/proxy-routes.json':['F82'],
'out/final-port/compat-recheck.log':['F01']}
for f in j['features']:
 f['validation_artifacts']=[path for path,ids in groups.items() if f['id'] in ids]
 if f['id']=='F59':f['validation_artifacts'].append('out/final-port/cron-timer.json')
 for path in f['validation_artifacts']:assert Path(path).exists(),path
 if f['status']=='implemented':assert f['validation_artifacts'],f['id']
Path('docs/audit/feature-parity-gap.json').write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
p=Path('docs/audit/feature-parity-gap.md');s=p.read_text().split('\n## 已实现项的交互与写盘验证索引')[0];s+='\n## 已实现项的交互与写盘验证索引\n\n'
s+='测试文件中包含真实 QTest 事件/写盘读回；涉及外部平台替身的限制在各行单独说明，不能外推系统成功态。最终完整运行日志 out/final-port/pytest-final.log。\n\n| 候选 | 证据文件 |\n|---|---|\n'
for f in j['features']:
 if f['status']=='implemented':s+='|'+f['id']+'|'+', '.join('`'+x+'`' for x in f['validation_artifacts'])+'|\n'
p.write_text(s)
