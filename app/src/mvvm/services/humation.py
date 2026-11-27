"""Bundled original Humation 1.0.3, evaluated by Qt (no Node at runtime)."""
import json
from pathlib import Path
from urllib.parse import quote
from utils.paths import assets_root


class Humation:
    def __init__(self):
        from utils.qt_compat import QtQml

        self.engine = QtQml.QJSEngine()
        path = assets_root() / 'humation' / 'runtime.js'
        if not path.exists(): path = Path(__file__).resolve().parents[3] / 'assets/humation/runtime.js'
        source = path.read_text()
        result = self.engine.evaluate('var globalThis = this; Array.prototype.flatMap = function(f) { return [].concat.apply([], this.map(f)); };\n' + source)
        if result.isError(): raise ValueError(result.toString())
        self.cache = {}

    def image(self, seed, spec, pop):
        key = (seed, spec, pop)
        if key not in self.cache:
            try: parsed = json.loads(spec) if spec else None
            except ValueError: parsed = None
            result = self.engine.evaluate('renderHumation(' + json.dumps(seed) + ',' + json.dumps(parsed) + ',' + str(pop).lower() + ')')
            if result.isError(): raise ValueError(result.toString())
            self.cache[key] = 'data:image/svg+xml,' + quote(result.toString())
        return self.cache[key]
