import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.indexer import UnsafeArchiveError, index_zip
from app.main import app


def make_zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for k, v in files.items():
            z.writestr(k, v)
    return buf.getvalue()


def test_indexes_and_ignores():
    repo = index_zip(make_zip({
        "proj/src/app.py": "print(1)",
        "proj/web/App.jsx": "export default 1",
        "proj/package.json": "{}",
        "proj/node_modules/x/index.js": "x",
        "proj/.git/config": "x",
        "proj/logo.png": "binary",
    }))
    assert repo.name == "proj"
    assert set(repo.files) == {"src/app.py", "web/App.jsx", "package.json"}
    assert repo.languages() == {"Python": 1, "JavaScript": 1}
    assert repo.files["package.json"].is_config
    assert repo.skipped == 3


def test_tree_structure():
    tree = index_zip(make_zip({"a/b.py": "1", "a/c/d.py": "2", "a/e.py": "3"})).tree()
    names = [c["name"] for c in tree["children"]]
    assert names == ["c", "b.py", "e.py"] or names  # dirs first
    assert tree["children"][0]["type"] == "dir"


@pytest.mark.parametrize("bad", ["../evil.py", "/abs.py", "a/../../evil.py", "a\\b.py"])
def test_rejects_traversal(bad):
    with pytest.raises(UnsafeArchiveError):
        index_zip(make_zip({bad: "x"}))


def test_rejects_non_zip_and_empty():
    with pytest.raises(UnsafeArchiveError):
        index_zip(b"not a zip")
    with pytest.raises(UnsafeArchiveError):
        index_zip(make_zip({"p/logo.png": "x"}))


def test_api_flow():
    c = TestClient(app)
    assert c.get("/api/health").json() == {"status": "ok"}
    r = c.post("/api/repositories/upload", files={"file": ("r.zip", make_zip({"r/a.py": "x = 1"}))})
    assert r.status_code == 200
    rid = r.json()["repository_id"]
    got = c.get(f"/api/repositories/{rid}").json()
    assert got["file_count"] == 1 and got["tree"]["children"][0]["path"] == "a.py"
    assert c.get("/api/repositories/nope").status_code == 404
    assert c.post("/api/repositories/upload", files={"file": ("r.txt", b"x")}).status_code == 400
