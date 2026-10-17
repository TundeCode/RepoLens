import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import gemma, prompts
from .indexer import Repository, UnsafeArchiveError, index_zip
from .ranking import (build_context, overview_context, rank_files, repo_index,
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


def call_model(prompt: str) -> dict:
    try:
        return gemma.generate_json(prompt)
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