"""Safe ZIP reading and repository indexing. Never executes uploaded code."""
import io
import posixpath
import zipfile
from collections import Counter
from dataclasses import dataclass, field

IGNORED_DIRS = {
    "node_modules", ".git", "venv", ".venv", "env", "__pycache__", "dist", "build",
    ".next", ".nuxt", "target", "out", "coverage", ".idea", ".vscode", ".pytest_cache",
}
LANGUAGES = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript",
    ".tsx": "TypeScript", ".java": "Java", ".go": "Go", ".rs": "Rust", ".rb": "Ruby",
    ".php": "PHP", ".c": "C", ".h": "C", ".cpp": "C++", ".cs": "C#", ".swift": "Swift",
    ".kt": "Kotlin", ".html": "HTML", ".css": "CSS", ".scss": "SCSS", ".vue": "Vue",
    ".svelte": "Svelte", ".sql": "SQL", ".sh": "Shell",
}
TEXT_EXTS = set(LANGUAGES) | {".json", ".yml", ".yaml", ".toml", ".md", ".txt", ".ini", ".cfg", ".env.example"}
CONFIG_NAMES = {
    "package.json", "requirements.txt", "pyproject.toml", "setup.py", "pom.xml",
    "build.gradle", "go.mod", "Cargo.toml", "Gemfile", "composer.json", "Dockerfile",
    "docker-compose.yml", "vite.config.js", "vite.config.ts", "tsconfig.json", "README.md",
}
MAX_FILE_BYTES = 200_000
MAX_TOTAL_UNCOMPRESSED = 200 * 1024 * 1024
MAX_ENTRIES = 20_000


class UnsafeArchiveError(ValueError):
    pass


@dataclass
class RepoFile:
    path: str
    language: str | None
    size: int
    content: str
    is_config: bool = False


@dataclass
class Repository:
    name: str
    files: dict[str, RepoFile] = field(default_factory=dict)
    skipped: int = 0

    def languages(self) -> dict[str, int]:
        return dict(Counter(f.language for f in self.files.values() if f.language).most_common())

    def tree(self) -> dict:
        root: dict = {"name": self.name, "path": "", "type": "dir", "children": []}
        for path in sorted(self.files):
            node, parts = root, path.split("/")
            for i, part in enumerate(parts):
                last = i == len(parts) - 1
                sub = "/".join(parts[: i + 1])
                found = next((c for c in node["children"] if c["name"] == part), None)
                if not found:
                    found = {"name": part, "path": sub, "type": "file" if last else "dir"}
                    if not last:
                        found["children"] = []
                    node["children"].append(found)
                node = found
        _sort(root)
        return root

    def metadata(self) -> dict:
        return {
            "name": self.name,
            "file_count": len(self.files),
            "languages": self.languages(),
            "config_files": sorted(p for p, f in self.files.items() if f.is_config),
            "skipped_files": self.skipped,
        }


def _sort(node: dict) -> None:
    if "children" in node:
        node["children"].sort(key=lambda c: (c["type"] != "dir", c["name"].lower()))
        for c in node["children"]:
            _sort(c)


def _clean_path(name: str) -> str:
    if name.startswith(("/", "\\")) or "\\" in name or ".." in name.split("/"):
        raise UnsafeArchiveError(f"Unsafe path in archive: {name!r}")
    norm = posixpath.normpath(name)
    if norm.startswith("..") or posixpath.isabs(norm) or (len(norm) > 1 and norm[1] == ":"):
        raise UnsafeArchiveError(f"Unsafe path in archive: {name!r}")
    return norm


def index_zip(data: bytes, fallback_name: str = "repository") -> Repository:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise UnsafeArchiveError("File is not a valid ZIP archive") from e

    infos = [i for i in zf.infolist() if not i.is_dir() and not i.filename.startswith("__MACOSX/")]
    if len(infos) > MAX_ENTRIES:
        raise UnsafeArchiveError("Archive has too many files")
    if sum(i.file_size for i in infos) > MAX_TOTAL_UNCOMPRESSED:
        raise UnsafeArchiveError("Archive is too large when extracted")

    entries = [(_clean_path(i.filename), i) for i in infos]  # raises on traversal

    # Strip a single shared top-level folder (GitHub-style ZIPs)
    tops = {p.split("/")[0] for p, _ in entries if "/" in p}
    single_root = len(tops) == 1 and all("/" in p for p, _ in entries)
    name = tops.pop() if single_root else fallback_name

    repo = Repository(name=name)
    for path, info in entries:
        rel = path.split("/", 1)[1] if single_root else path
        parts = rel.split("/")
        if any(p in IGNORED_DIRS for p in parts[:-1]):
            repo.skipped += 1
            continue
        base = parts[-1]
        ext = posixpath.splitext(base)[1].lower()
        if ext not in TEXT_EXTS and base not in CONFIG_NAMES:
            repo.skipped += 1
            continue
        if info.file_size > MAX_FILE_BYTES:
            repo.skipped += 1
            continue
        raw = zf.read(info)
        if b"\x00" in raw[:1024]:
            repo.skipped += 1
            continue
        repo.files[rel] = RepoFile(
            path=rel, language=LANGUAGES.get(ext), size=info.file_size,
            content=raw.decode("utf-8", errors="replace"), is_config=base in CONFIG_NAMES,
        )
    if not repo.files:
        raise UnsafeArchiveError("No supported source files found in archive")
    return repo
