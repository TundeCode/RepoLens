from fastapi.testclient import TestClient

from app import gemma, main
from app.indexer import index_zip
from app.ranking import rank_ui_files
from tests.test_indexer import make_zip

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
FILES = {
    "r/src/pages/Login.jsx": "export default () => <button>Sign in with Google</button>\n",
    "r/src/pages/Home.jsx": "export default () => <h1>Welcome</h1>\n",
    "r/server/db.py": "def query(): pass\n",
}


def test_sniff_image():
    assert main.sniff_image(PNG) == "image/png"
    assert main.sniff_image(b"\xff\xd8\xff\xe0abc") == "image/jpeg"
    assert main.sniff_image(b"RIFF1234WEBPxxxx") == "image/webp"
    assert main.sniff_image(b"<svg></svg>") is None


def test_visible_text_drives_ranking():
    repo = index_zip(make_zip(FILES))
    top = rank_ui_files(repo, ["Sign in with Google"], "")[0]
    assert top.path == "src/pages/Login.jsx"


def test_endpoint_grounded_and_validated(monkeypatch):
    def fake(prompt, image=None):
        assert image is not None
        if "first pass" in prompt:
            return {"screen_summary": "Login screen", "matches": [
                {"path": "src/pages/Login.jsx", "role": "page", "reason": "login", "evidence": "Sign in button",
                 "confidence": "high", "start_line": 1, "end_line": 1},
                {"path": "src/ghost.jsx", "reason": "invented", "confidence": "bogus"}],
                "uncertainty": "", "overall_confidence": "high"}
        return {"summary": "A login page", "visible_text": ["Sign in with Google"], "keywords": ["login"], "page_type": "login"}
    monkeypatch.setattr(gemma, "generate_json", fake)
    c = TestClient(main.app)
    rid = c.post("/api/repositories/upload", files={"file": ("r.zip", make_zip(FILES))}).json()["repository_id"]
    r = c.post(f"/api/repositories/{rid}/screenshot", files={"file": ("s.png", PNG)}, data={"question": ""})
    assert r.status_code == 200
    out = r.json()
    assert [m["path"] for m in out["matches"]] == ["src/pages/Login.jsx"]
    assert out["matches"][0]["snippet"].startswith("export default")
    assert out["removed_unverified_paths"] == ["src/ghost.jsx"]
    assert out["files_considered"][0] == "src/pages/Login.jsx"


def test_rejects_non_image_and_oversize():
    c = TestClient(main.app)
    rid = c.post("/api/repositories/upload", files={"file": ("r.zip", make_zip(FILES))}).json()["repository_id"]
    assert c.post(f"/api/repositories/{rid}/screenshot", files={"file": ("x.png", b"not an image")}).status_code == 400
    big = PNG + b"\x00" * (main.MAX_IMAGE_BYTES + 1)
    assert c.post(f"/api/repositories/{rid}/screenshot", files={"file": ("x.png", big)}).status_code == 413
    assert c.post("/api/repositories/nope/screenshot", files={"file": ("x.png", PNG)}).status_code == 404
