"""Exercise every display template without translating protocol payloads."""
import json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'app/src'))
from locale_runtime import catalogues,display_text
errors=[]
count=0
for key,source in catalogues()['zh-CN'].items():
    if not key.startswith('display.'):
        continue
    value=source
    for name in re.findall(r'\{([A-Za-z][A-Za-z0-9_]*)\}',source):
        value=value.replace('{'+name+'}',name.upper())
    shown=display_text(value)
    count+=1
    if re.search('[\u4e00-\u9fff]',shown):
        errors.append(dict(key=key,input=value,shown=shown))
print(json.dumps(dict(display_templates=count,chinese_residuals_in_english=errors),ensure_ascii=False,indent=2))
assert not errors
