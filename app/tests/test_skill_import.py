"""F70：技能 .md/.zip 导入，校验目录、启用位与 zip-slip。"""
from __future__ import annotations
import io, zipfile
from pathlib import Path
from mvvm.services.skill_store import SkillStore


def test_import_markdown_and_zip(tmp_path):
    store = SkillStore(tmp_path)
    md = tmp_path / "demo.md"
    md.write_text("---\nname: Demo Skill\ndescription: demo\n---\n\n# Demo\n", encoding="utf-8")
    result = store.import_file(md)
    assert result == {"ok": True, "id": "demo-skill", "name": "Demo Skill"}
    assert (tmp_path / "skills" / "demo-skill" / "SKILL.md").is_file()
    assert store.get("demo-skill")["enabled"] is True

    package = tmp_path / "pack.zip"
    with zipfile.ZipFile(package, "w") as z:
        z.writestr("pack/SKILL.md", "---\nname: Zip Skill\ndescription: zip\n---\n\nbody\n")
        z.writestr("pack/scripts/run.sh", "echo hi\n")
    result = store.import_file(package)
    assert result["ok"] and result["id"] == "zip-skill"
    assert (tmp_path / "skills" / "zip-skill" / "scripts" / "run.sh").read_text() == "echo hi\n"

    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("SKILL.md", "---\nname: Bad\n---\n")
        z.writestr("../escape.txt", "x")
    assert store.import_file(bad)["error"] == "unsafe-path"
