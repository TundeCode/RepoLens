import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .indexer import Repository, UnsafeArchiveError, index_zip

load_dotenv()
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024

app = FastAPI(title="RepoLens")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)

REPOS: dict[str, Repository] = {}  # in-memory sessions


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
