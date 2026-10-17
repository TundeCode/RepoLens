# RepoLens

**Understand any codebase in minutes, not hours.**

RepoLens is an AI-powered repository onboarding assistant built on **Google's Gemma 4** (via the Gemini API). Upload a repo as a ZIP and RepoLens explains how it works, points you to the right files for a task, and can match a UI screenshot to the code that renders it.

It does not write code for you. It helps you **navigate and understand** code that already exists.

## Features

- **Repository overview**: purpose, languages, frameworks, architecture, entry points, key files, and where to start. Anything it can't determine is listed as unknown.
- **"Where do I start?"**: ask things like *"Where would I add Google authentication?"* and get ordered file recommendations with reasons and line references.
- **Screenshot to code**: upload a UI screenshot; Gemma reads it, then matches it to likely components, pages, and styles, with evidence and a confidence level.

## How Gemma 4 is used

| Task | Input | What Gemma does |
|---|---|---|
| Overview | file index + config/entry-point files | Summarizes the project from real contents |
| Ask | question + top-ranked files with line numbers | Explains and recommends files in a suggested order |
| Screenshot | image, then image + candidate files | Pass 1 reads the visible text/UI; pass 2 matches it to code |

Default model: `gemma-4-26b-a4b-it` (also available: `gemma-4-31b-it`). The server refuses any model name that doesn't start with `gemma-4`, so it never silently falls back to a different model.

## How answers stay grounded

AI models can invent file names. RepoLens checks everything the model returns:

1. File paths are validated against the uploaded repository; invented paths are dropped and reported.
2. Line ranges are checked against the real file length.
3. Code snippets shown in the UI are copied from your actual files by the server, never from model text.
4. Prompts require the model to say "unknown" instead of guessing.

AI output can still be wrong, so verify before relying on it.

## Security

- Uploaded code is only read as text, never executed.
- ZIP uploads are checked for path traversal, entry count, and extracted size (zip bombs).
- Upload size limits: 50 MB for repos, 5 MB for screenshots. Screenshot type is detected from file bytes, not the client's claim.
- The API key is read from an environment variable and never sent to the browser.

## Architecture

```
Frontend (React + Vite + Tailwind)  --/api-->  Backend (FastAPI)
                                                 ├─ indexer.py   safe ZIP reading, file tree
                                                 ├─ ranking.py   keyword/path ranking, grounding checks
                                                 ├─ prompts.py   task prompts
                                                 └─ gemma.py     all Gemma 4 calls (text + image)
```
Sessions live in memory (no database), so restarting the backend clears uploaded repos.

## Setup

**Requirements:** Python 3.10+, Node 18+, and a Gemini API key from https://aistudio.google.com/apikey

**1. Backend**
```
cd Backend
python3 -m pip install -r requirements.txt
cp .env.example .env        # then put your key in .env
python3 -m app.list_models  # confirms your key can see Gemma 4
python3 -m uvicorn app.main:app --reload
```
Check http://127.0.0.1:8000/api/health shows `{"status":"ok"}`.

**2. Frontend** (second terminal)
```
cd Frontend
npm install
npm run dev
```
Open http://localhost:5173.

**3. Tests**
```
cd Backend
python3 -m pytest
```

## Environment variables (`Backend/.env`)

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Your Gemini API key (required) |
| `GEMMA_MODEL` | Gemma 4 model id (default `gemma-4-26b-a4b-it`) |
| `MAX_UPLOAD_MB` | Repo ZIP size limit (default 50) |

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Health check |
| POST | `/api/repositories/upload` | Upload a ZIP, returns repository id + metadata |
| GET | `/api/repositories/{id}` | Metadata and file tree |
| GET | `/api/repositories/{id}/overview` | AI overview |
| POST | `/api/repositories/{id}/ask` | Body `{"question": "..."}` returns file recommendations |
| POST | `/api/repositories/{id}/screenshot` | Multipart `file` (+ optional `question`) returns matches |

Interactive docs at http://127.0.0.1:8000/docs.

## Limitations

- Large repos are only partly sent to the model (context is capped, and files are chosen by keyword/path matching, not embeddings).
- Files over 200 KB and binary files are skipped.
- Screenshot matching works best when the screenshot contains readable text that also appears in the code.
- Results are AI-generated and can be incomplete or wrong.
