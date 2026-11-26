"""Reproducible catalogue/key audit; Python literals are candidates, not UI counts."""
import ast
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out/i18n'
OUT.mkdir(parents=True, exist_ok=True)
locales = {p.stem: json.loads(p.read_text()) for p in (ROOT / 'app/src/locales').glob('*.json')}
keys = set().union(*(set(d) for d in locales.values()))
used = []
for p in (ROOT / 'app/src/qml').glob('*.qml'):
    for n, line in enumerate(p.read_text().splitlines(), 1):
        if line.lstrip().startswith('//'):
            continue
        used.extend({'file': str(p.relative_to(ROOT)), 'line': n, 'key': m[1]}
                    for m in re.finditer(r'I18n.t\("([^"\n]+)"\)', line))
coverage = {locale: {'keys': len(d), 'missing': sorted(keys - set(d)),
                     'missing_used': sorted({r['key'] for r in used} - set(d)),
                     'empty': [k for k,v in d.items() if not v]}
            for locale, d in locales.items()}
(OUT / 'coverage.json').write_text(json.dumps(coverage, ensure_ascii=False, indent=2)+'\n')
(OUT / 'bindings.json').write_text(json.dumps(used, ensure_ascii=False, indent=2)+'\n')
rows = []
for base in ('app/src', 'tools'):
    for p in (ROOT / base).rglob('*.py'):
        if p.name == 'audit_i18n.py':
            continue
        tree = ast.parse(p.read_text())
        docs = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Expr)
                and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
                s = node.value
                if re.search(r'[\u4e00-\u9fff]|[A-Za-z]+ [A-Za-z]+', s):
                    rows.append({'file': str(p.relative_to(ROOT)), 'line': node.lineno, 'text': s})
(OUT / 'python-literal-candidates.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'coverage': coverage, 'qml_bindings': len(used), 'qml_files': len({r['file'] for r in used}), 'python_candidate_literals': len(rows), 'python_candidate_files': len({r['file'] for r in rows})},ensure_ascii=False,indent=2))
assert all(not d['missing'] and not d['missing_used'] for d in coverage.values())
