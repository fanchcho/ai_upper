"""Inventory literal candidates without claiming semantic review by a heuristic."""
import ast,json,re
from pathlib import Path
root=Path(__file__).resolve().parents[3]
rows=[]
for base in ('app/src','tools'):
 for p in (root/base).rglob('*.py'):
  tree=ast.parse(p.read_text());parent={c:n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
  for n in ast.walk(tree):
   if not isinstance(n,ast.Constant) or not isinstance(n.value,str):continue
   if not re.search(r'[\u4e00-\u9fff]|[A-Za-z]+ [A-Za-z]+',n.value):continue
   par=parent.get(n)
   status='needs_review';reason='requires semantic classification'
   if isinstance(par,ast.Expr):status='out_of_scope';reason='docstring or standalone documentation'
   elif isinstance(par,ast.Call) and isinstance(par.func,ast.Name) and par.func.id=='tr':status='resolved';reason='catalogue lookup key'
   elif '/_vendor/' in str(p):status='out_of_scope';reason='vendored parser diagnostics; source retained'
   rows.append(dict(file=str(p.relative_to(root)),line=n.lineno,text=n.value,status=status,reason=reason))
(root/'out/i18n/close/scan.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({s:sum(r['status']==s for r in rows) for s in ('resolved','out_of_scope','needs_review')}))
