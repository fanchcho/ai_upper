import json

from ai_upper.config import TARGETS, project_version
from ai_upper.package import write_release_manifest


def test_supporting_trees_ship_beside_the_launcher_payload(tmp_path, monkeypatch):
    """`app/assets` is part of the payload, not a development-only detail.

    The packaged shell loads its QML from `<bundle>/assets/qml` and its seed
    personas from `<bundle>/assets/personas`; a bundle without them starts with
    an empty window and says nothing. Both trees are optional, but when present
    they must land where `utils.paths` reads them.
    """
    from ai_upper import package as pkg

    app = tmp_path / "app"
    (app / "assets" / "personas").mkdir(parents=True)
    (app / "assets" / "personas" / "general.md").write_text("# 通用", encoding="utf-8")
    (app / "src" / "qml").mkdir(parents=True)
    (app / "src" / "qml" / "Main.qml").write_text("import QtQuick\nItem {}\n", encoding="utf-8")
    (app / "resources").mkdir()
    (app / "resources" / "logo.png").write_bytes(b"\x89PNG")
    monkeypatch.setattr(pkg, "APP", app)

    out = tmp_path / "bundle"
    pkg._copy_supporting_trees(out)

    assert (out / "assets" / "personas" / "general.md").read_text(encoding="utf-8") == "# 通用"
    # The QML tree is not under app/assets: the engine loads it from
    # <bundle>/assets/qml, so packaging has to put it there.
    assert (out / "assets" / "qml" / "Main.qml").is_file()
    assert (out / "resources" / "logo.png").read_bytes() == b"\x89PNG"

    # Neither tree is required: a project without them packages fine.
    empty = tmp_path / "empty"
    monkeypatch.setattr(pkg, "APP", empty)
    empty_out = tmp_path / "empty-bundle"
    pkg._copy_supporting_trees(empty_out)
    assert not empty_out.exists()


def test_release_manifest_is_deterministic_and_hashed(tmp_path):
    out = tmp_path / "dist"
    (out / "DemoApp").mkdir(parents=True)
    (out / "DemoApp" / "DemoApp").write_bytes(b"launcher")
    path = write_release_manifest(TARGETS["linux-x86_64"], out)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == project_version()
    assert data["target"] == "linux-x86_64"
    assert data["files"][0]["path"] == "DemoApp/DemoApp"
    assert len(data["files"][0]["sha256"]) == 64
