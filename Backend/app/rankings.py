"""Keyword/path file ranking, context building, and grounding validation (no vector DB)."""
import posixpath
import re

from .indexer import RepoFile, Repository

STOP = {"the", "and", "for", "how", "where", "what", "which", "does", "work", "works", "would",
        "should", "want", "with", "this", "that", "from", "into", "add", "new", "need", "code",
        "file", "files", "implement", "start", "handle", "handles", "have", "can", "use"}
SYNONYMS = {
    "auth": ["auth", "login", "signin", "signup", "oauth", "session", "token", "jwt", "password", "user"],
    "login": ["login", "signin", "auth", "session", "password"],
    "google": ["google", "oauth", "openid"],
    "database": ["database", "db", "sql", "model", "models", "schema", "query", "orm", "migration"],
    "dark": ["dark", "theme", "themes", "color", "colors", "style", "styles", "css", "tailwind"],
    "theme": ["theme", "dark", "color", "style", "css"],
    "api": ["api", "route", "routes", "router", "endpoint", "controller", "view", "views"],
    "endpoint": ["endpoint", "route", "routes", "router", "api", "view", "controller"],
    "test": ["test", "tests", "spec", "pytest", "jest"],
}
ENTRY_NAMES = {"main.py", "app.py", "manage.py", "server.js", "index.js", "index.ts", "main.js",
               "main.ts", "main.go", "App.jsx", "App.tsx", "main.jsx", "main.tsx", "index.html"}


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2 and t not in STOP]


def expand(tokens: list[str]) -> set[str]:
    terms = set(tokens)
    for key, group in SYNONYMS.items():
        if any(t.startswith(key) for t in tokens):
            terms.update(group)
    return terms


def score_file(f: RepoFile, terms: set[str]) -> int:
    path = f.path.lower()
    name = posixpath.basename(path)
    body = f.content.lower()
    score = 0
    for t in terms:
        if t in path:
            score += 4
        if t in name:
            score += 2
        score += min(body.count(t), 5)
    return score if f.language else score // 2  # prefer source over docs/config


def rank_files(repo: Repository, question: str, limit: int = 8) -> list[RepoFile]:
    terms = expand(tokenize(question))
    scored = sorted(((score_file(f, terms), f.path) for f in repo.files.values()), reverse=True)
    picked = [repo.files[p] for s, p in scored if s > 0][:limit]
    if not picked:  # fall back to entry points + config so the model still has context
        picked = [f for f in repo.files.values() if f.is_config or posixpath.basename(f.path) in ENTRY_NAMES][:limit]
    return picked


def numbered(content: str, max_lines: int = 400) -> str:
    lines = content.splitlines()
    out = [f"{i}| {l}" for i, l in enumerate(lines[:max_lines], 1)]
    if len(lines) > max_lines:
        out.append(f"... [truncated, {len(lines) - max_lines} more lines]")
    return "\n".join(out)


def build_context(files: list[RepoFile], budget: int = 60_000) -> str:
    parts, used = [], 0
    for f in files:
        block = f"=== FILE: {f.path} ({len(f.content.splitlines())} lines) ===\n{numbered(f.content)}\n"
        if used + len(block) > budget:
            block = block[: max(0, budget - used)]
        if not block:
            break
        parts.append(block)
        used += len(block)
    return "\n".join(parts)


def repo_index(repo: Repository, max_paths: int = 400) -> str:
    paths = sorted(repo.files)
    text = "\n".join(paths[:max_paths])
    if len(paths) > max_paths:
        text += f"\n... and {len(paths) - max_paths} more files"
    return text


def overview_context(repo: Repository, budget: int = 40_000) -> str:
    key = [f for f in repo.files.values() if f.is_config or posixpath.basename(f.path) in ENTRY_NAMES]
    key.sort(key=lambda f: (not f.is_config, f.path))
    return build_context(key[:15], budget)


# ---- grounding: never trust model-provided paths/lines ----
def _as_int(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def validate_paths(repo: Repository, paths: list) -> tuple[list[str], list[str]]:
    ok, bad = [], []
    for p in paths if isinstance(paths, list) else []:
        p = str(p).strip().lstrip("./")
        (ok if p in repo.files else bad).append(p)
    return ok, bad


def validate_recs(repo: Repository, recs: list, snippet_lines: int = 40) -> tuple[list[dict], list[str]]:
    valid, dropped = [], []
    for r in recs if isinstance(recs, list) else []:
        if not isinstance(r, dict):
            continue
        path = str(r.get("path", "")).strip().lstrip("./")
        if path not in repo.files:
            dropped.append(path)
            continue
        lines = repo.files[path].content.splitlines()
        s, e = _as_int(r.get("start_line")), _as_int(r.get("end_line"))
        snippet = None
        if s and e and 1 <= s <= e <= len(lines):
            e = min(e, s + snippet_lines - 1)
            snippet = "\n".join(lines[s - 1:e])  # taken from the real file, not the model
        else:
            s = e = None
        valid.append({"path": path, "reason": str(r.get("reason", "")), "start_line": s,
                      "end_line": e, "snippet": snippet})
    return valid, dropped
