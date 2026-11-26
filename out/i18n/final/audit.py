"""Recheck the frozen review and current Python/QML inventory; unknowns fail closed."""
import ast,collections,csv,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'out/i18n/final'
read=lambda name:json.loads((OUT/name).read_text())
baseline=read('baseline-scan.json')
review=read('review-742.json')
expected=[r for r in baseline if r['status']=='needs_review']
assert len(expected)==len(review)==742
categories={'catalogue','model_protocol','machine_output','log_debug','upstream','deva_reference'}
for i,(a,b) in enumerate(zip(expected,review)):
    assert b['id']==i and all(a[k]==b[k] for k in ('file','line','text'))
    assert b['status'] in ('resolved','out_of_scope') and b['category'] in categories and b['reason']
    if b['status']=='resolved':assert b['key']
lookup={(r['file'],r['text']):r for r in baseline if r['status']!='needs_review'}
lookup.update({(r['file'],r['text']):r for r in review})
for r in read('extra-review.json'):lookup[(r['file'],r['text'])]=r
catalogs={loc:json.loads((ROOT/'app/src/locales'/f'{loc}.json').read_text()) for loc in ('en','zh-CN')}
all_keys=set().union(*(set(c) for c in catalogs.values()))
coverage={loc:dict(keys=len(c),missing=sorted(all_keys-set(c)),empty=[k for k,v in c.items() if not v and k != 'app.tagline'],intentional_empty={'app.tagline':'沿用原版两种语言的空副标题，不显示文案'}) for loc,c in catalogs.items()}
rows=[];calls=[];errors=[]
for base in ('app/src','tools'):
    for p in sorted((ROOT/base).rglob('*.py')):
        file=str(p.relative_to(ROOT));t=ast.parse(p.read_text());parents={c:n for n in ast.walk(t) for c in ast.iter_child_nodes(n)}
        for n in ast.walk(t):
            if isinstance(n,ast.Call):
                name=n.func.id if isinstance(n.func,ast.Name) else ''
                pos=1 if name=='translate' else 0
                if name in ('tr','translate','_boot_tr') and len(n.args)>pos and isinstance(n.args[pos],ast.Constant) and isinstance(n.args[pos].value,str):
                    key=n.args[pos].value;missing=key not in all_keys
                    # Positional placeholders are interpolated here; named templates may deliberately be formatted by the caller.
                    needed=set(re.findall(r'\{(p\d+)\}',catalogs['en'].get(key,'')))
                    supplied={k.arg for k in n.keywords};absent=sorted(needed-supplied) if name=='tr' else []
                    item=dict(file=file,line=n.lineno,key=key,missing_key=missing,missing_params=absent);calls.append(item)
                    if missing or absent:errors.append(item)
            if not isinstance(n,ast.Constant) or not isinstance(n.value,str) or not re.search(r'[\u4e00-\u9fff]|[A-Za-z]+ [A-Za-z]+',n.value):continue
            before=lookup.get((file,n.value));par=parents.get(n)
            item=dict(file=file,line=n.lineno,text=n.value)
            if isinstance(par,ast.Expr):item.update(status='out_of_scope',category='log_debug',reason='Python __doc__ 文档元数据，非 UI/CLI 运行展示；源码注释说明保留')
            elif before:
                if before['status']=='resolved' and file!='tools/ai_upper/egg_loader.py':
                    item.update(status='needs_review',category='',reason='已迁移原文重新出现在源码中，必须复核')
                else:item.update(status=before['status'],category=before.get('category','upstream'),reason=before['reason'],key=before.get('key',''))
            else:item.update(status='needs_review',category='',reason='新增或改变的字面量未审核')
            rows.append(item)
qml_known={(r['file'],r['text']):r for r in read('qml-review.json')}
pattern=re.compile(r'"(?:\\.|[^"\\])*"|\x27(?:\\.|[^\x27\\])*\x27')
for p in sorted((ROOT/'app/src/qml').rglob('*.qml')):
    file=str(p.relative_to(ROOT))
    for number,line in enumerate(p.read_text().splitlines(),1):
        if line.lstrip().startswith('//'):continue
        for m in pattern.finditer(line):
            value=m.group()[1:-1]
            if not re.search('[A-Za-z\u4e00-\u9fff]',value):continue
            b=qml_known.get((file,value),{})
            r=dict(b,file=file,line=number,text=value,status=b.get('status','needs_review'))
            if re.search(r'I18n\.t\(\s*$',line[:m.start()]):
                r.update(status='resolved',category='catalogue',reason='I18n.t 资源键',key=value)
                if value not in all_keys:errors.append(r)
            rows.append(r)
for r in review:
    if r.get('key') and r['key'] not in all_keys:errors.append(r)
counts=dict(collections.Counter(r['status'] for r in rows));counts.setdefault('needs_review',0)
result=dict(baseline_review=dict(collections.Counter(r['status'] for r in review)),current_scan=counts,coverage=coverage,python_translation_calls=len(calls),translation_call_errors=errors)
for name,data in [('current-scan.json',rows),('translation-calls.json',calls),('summary.json',result)]:
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
with (OUT/'current-scan.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['file','line','text','status','category','key','reason'],extrasaction='ignore');w.writeheader();w.writerows(rows)
print(json.dumps(result,ensure_ascii=False,indent=2))
assert not counts['needs_review'] and not errors and all(not c['missing'] and not c['empty'] for c in coverage.values())
