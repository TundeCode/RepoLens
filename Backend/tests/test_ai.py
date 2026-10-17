import pytest
from fastapi.testclient import TestClient

from app import gemma, main
from app.indexer import index_zip
from app.ranking import rank_files, validate_recs
from tests.test_indexer import make_zip

FILES = {
    "r/server/auth.py": "def login(user):\n    return create_token(user)\n\ndef logout():\n    pass\n",
    "r/server/db.py": "import sqlite3\ndef query(sql):\n    pass\n",
    "r/web/src/Login.jsx": "export default function Login(){ return null }\n",
    "r/web/src/theme.css": "body { color: white }\n",
    "r/requirements.txt": "fastapi\n",
}


@pytest.fixture
def repo():
    return index_zip(make_zip(FILES))


def test_ranking_prefers_relevant(repo):
    top = [f.path for f in rank_files(repo, "How does the login system work?")][:2]
    assert "server/auth.py" in top and "web/src/Login.jsx" in top


def test_synonym_expansion_finds_theme(repo):
    assert rank_files(repo, "I want to add dark mode")[0].path == "web/src/theme.css"


def test_validation_drops_fake_paths_and_lines(repo):
    recs = [{"path": "server/auth.py", "reason": "x", "start_line": 1, "end_line": 2},
            {"path": "server/fake.py", "reason": "y"},
            {"path": "server/db.py", "reason": "z", "start_line": 1, "end_line": 999}]
    valid, dropped = validate_recs(repo, recs)
    assert dropped == ["server/fake.py"]
    assert valid[0]["snippet"] == "def login(user):\n    return create_token(user)"
    assert valid[1]["start_line"] is None and valid[1]["snippet"] is None


def test_parse_json_handles_fences():
    assert gemma.parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    with pytest.raises(ValueError):
        gemma.parse_json("nope")


def test_non_gemma4_model_rejected(monkeypatch):
    monkeypatch.setenv("GEMMA_MODEL", "gemini-2.5-flash")
    with pytest.raises(gemma.GemmaError):
        gemma.model_name()


def test_ask_endpoint_grounded(monkeypatch):
    monkeypatch.setattr(gemma, "generate_json", lambda p: {
        "summary": "Start in auth.", "files": [
            {"path": "server/auth.py", "reason": "login logic", "start_line": 1, "end_line": 2},
            {"path": "ghost.py", "reason": "invented"}],
        "exploration_order": ["server/auth.py", "ghost.py"], "related_to_inspect": [], "caveats": []})
    c = TestClient(main.app)
    rid = c.post("/api/repositories/upload", files={"file": ("r.zip", make_zip(FILES))}).json()["repository_id"]
    out = c.post(f"/api/repositories/{rid}/ask", json={"question": "How does login work?"}).json()
    assert [f["path"] for f in out["files"]] == ["server/auth.py"]
    assert out["removed_unverified_paths"].count("ghost.py") == 2
    assert c.get(f"/api/repositories/{rid}/overview").status_code in (200, 503)


def test_missing_key_gives_503(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    c = TestClient(main.app)
    rid = c.post("/api/repositories/upload", files={"file": ("r.zip", make_zip(FILES))}).json()["repository_id"]
    assert c.get(f"/api/repositories/{rid}/overview").status_code == 503
