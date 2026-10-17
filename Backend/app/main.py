import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import gemma, prompts
from .indexer import Repository, UnsafeArchiveError, index_zip
from .ranking import (build_context, overview_context, rank_files, rank_ui_files, repo_index,
                      validate_paths, validate_recs)

load_dotenv()
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024

app = FastAPI(title="RepoLens")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)

REPOS: dict[str, Repository] = {}  # in-memory sessions
OVERVIEWS: dict[str, dict] = {}


def get_repo(repository_id: str) -> Repository:
    repo = REPOS.get(repository_id)
    if not repo:
        raise HTTPException(404, "Repository not found")
    return repo


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/repositories/upload")
async def upload(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(400, "Please upload a .zip file")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File exceeds {MAX_UPLOAD_BYTES // 1024 // 1024} MB limit")
    try:
        repo = index_zip(data, fallback_name=(file.filename or "repository")[:-4])
    except UnsafeArchiveError as e:
        raise HTTPException(400, str(e))
    repo_id = uuid.uuid4().hex[:12]
    REPOS[repo_id] = repo
    return {"repository_id": repo_id, **repo.metadata()}


@app.get("/api/repositories/{repository_id}")
def get_repository(repository_id: str):
    repo = get_repo(repository_id)
    return {"repository_id": repository_id, **repo.metadata(), "tree": repo.tree()}


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


def call_model(prompt: str, image=None) -> dict:
    try:
        return gemma.generate_json(prompt) if image is None else gemma.generate_json(prompt, image=image)
    except gemma.GemmaError as e:
        raise HTTPException(e.status, str(e))


@app.get("/api/repositories/{repository_id}/overview")
def overview(repository_id: str):
    repo = get_repo(repository_id)
    if repository_id in OVERVIEWS:
        return OVERVIEWS[repository_id]
    raw = call_model(prompts.OVERVIEW.format(
        rules=prompts.RULES, index=repo_index(repo), context=overview_context(repo)))
    key_files, dropped = validate_recs(repo, [{"path": k.get("path"), "reason": k.get("why")}
                                              for k in raw.get("key_files", []) if isinstance(k, dict)])
    entry, bad_entry = validate_paths(repo, raw.get("entry_points", []))
    result = {
        "purpose": raw.get("purpose", ""), "languages": raw.get("languages", []),
        "frameworks": raw.get("frameworks", []), "architecture": raw.get("architecture", ""),
        "key_files": [{"path": k["path"], "why": k["reason"]} for k in key_files],
        "entry_points": entry, "component_interactions": raw.get("component_interactions", ""),
        "start_here": raw.get("start_here", []), "unknowns": raw.get("unknowns", []),
        "removed_unverified_paths": dropped + bad_entry,
        "disclaimer": "AI-generated from repository contents; verify before relying on it.",
    }
    OVERVIEWS[repository_id] = result
    return result


@app.post("/api/repositories/{repository_id}/ask")
def ask(repository_id: str, body: AskRequest):
    repo = get_repo(repository_id)
    candidates = rank_files(repo, body.question)
    raw = call_model(prompts.ASK.format(
        rules=prompts.RULES, question=body.question, index=repo_index(repo),
        context=build_context(candidates)))
    files, dropped = validate_recs(repo, raw.get("files", []))
    order, bad_order = validate_paths(repo, raw.get("exploration_order", []))
    related, bad_rel = validate_paths(repo, raw.get("related_to_inspect", []))
    return {
        "question": body.question, "summary": raw.get("summary", ""), "files": files,
        "exploration_order": order, "related_to_inspect": related,
        "caveats": raw.get("caveats", []),
        "removed_unverified_paths": dropped + bad_order + bad_rel,
        "files_considered": [f.path for f in candidates],
        "disclaimer": "AI-generated from repository contents; verify before relying on it.",
    }


MAX_IMAGE_BYTES = 5 * 1024 * 1024
DEFAULT_SCREEN_Q = "Which files in this repository are responsible for this screen?"


def sniff_image(data: bytes) -> str | None:
    """Detect the real image type from file bytes; never trust the client's content-type."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


@app.post("/api/repositories/{repository_id}/screenshot")
def screenshot(repository_id: str, file: UploadFile = File(...), question: str = Form("")):
    repo = get_repo(repository_id)
    data = file.file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image exceeds the 5 MB limit")
    mime = sniff_image(data)
    if not mime:
        raise HTTPException(400, "Please upload a PNG, JPEG, or WebP image")
    image = (data, mime)
    user_q = question.strip()[:500]

    # Pass 1: read the screenshot. Pass 2: match it against the most likely UI files.
    desc = call_model(prompts.DESCRIBE, image)
    visible = [t for t in desc.get("visible_text", []) if isinstance(t, str)][:25]
    words = [k for k in desc.get("keywords", []) if isinstance(k, str)]
    candidates = rank_ui_files(repo, visible, " ".join(words) + " " + str(desc.get("page_type", "")) + " " + user_q)
    raw = call_model(prompts.SCREENSHOT.format(
        rules=prompts.RULES, question=user_q or DEFAULT_SCREEN_Q,
        description=str(desc.get("summary", "")), index=repo_index(repo),
        context=build_context(candidates)), image)

    matches, dropped = validate_recs(repo, raw.get("matches", []), extra=("role", "evidence", "confidence"))
    for m in matches:
        m["confidence"] = m["confidence"] if m["confidence"] in ("high", "medium", "low") else "low"
    overall = raw.get("overall_confidence")
    return {
        "screen_summary": raw.get("screen_summary") or str(desc.get("summary", "")),
        "visible_text": visible, "matches": matches,
        "uncertainty": raw.get("uncertainty", ""),
        "overall_confidence": overall if overall in ("high", "medium", "low") else "low",
        "removed_unverified_paths": dropped,
        "files_considered": [f.path for f in candidates],
        "disclaimer": "AI-generated from the screenshot and repository contents; verify before relying on it.",
    }