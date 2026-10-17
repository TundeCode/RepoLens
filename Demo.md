# RepoLens Demo Guide

## Before you present
- [ ] Backend and frontend both running; `/api/health` returns ok
- [ ] `Backend/.env` has your key; `python3 -m app.list_models` shows a Gemma 4 model
- [ ] Upload your demo repo once and run every question below, so you know what to expect (the first Gemma call can be slow)
- [ ] Have a screenshot of the demo app ready (PNG, under 5 MB)
- [ ] `git status` shows no `.env`; repo is pushed

## Pick the right demo repo
Use a repo you know well, with a real backend and frontend and some AI/DB code. Your `hackathon-10-18-main` repo works well: it has `gemini_client.py`, `app.py`, `files_api.py`, and a frontend, and you can check every answer yourself.

## Questions that make good demos
| Question | Why it works |
|---|---|
| Where is the Gemini client used? | Easy to verify; shows exact files and lines |
| How does file upload work end to end? | Shows how backend and frontend connect |
| Where should I add a new API endpoint? | The core "where do I start" use case |
| Where would I add user authentication? | If the repo has none, shows RepoLens saying so instead of inventing files |
| I want to change the page styling. Where do I start? | Lands on the CSS and HTML files |

**Keep one "trap" question.** Ask about something the repo doesn't have (like login on a repo with no login). A good result says it can't find it, which proves the grounding.

## 3-minute script
1. **Problem (20s):** "Joining a new codebase takes hours. Existing AI tools help you write code; RepoLens helps you understand it."
2. **Upload (20s):** drop the ZIP. Point out the file tree, language counts, and that code is read but never executed.
3. **Overview (30s):** walk through purpose, architecture, entry points. Mention the "could not determine" section.
4. **Ask (60s):** run two questions. Open "Show code" on one card and show the real line numbers. Run the trap question.
5. **Screenshot (40s):** drop the screenshot, show the matches, evidence, and confidence level.
6. **Close (10s):** "Gemma 4 handles text, code, and images. Every file path is checked against the real repo before you see it."

## Talking points for judges
- **Gemma 4 is the only model:** overview, Q&A, and screenshot analysis all use it; the server rejects any non-Gemma-4 model name.
- **Multimodal:** text + code + image, with a two-pass screenshot flow (read the UI, then match it to code).
- **Grounding:** invented file paths are dropped and reported; snippets come from the real file.
- **Honest uncertainty:** confidence levels, "unknown" lists, and visible disclaimers.
- **Safe by design:** no code execution, ZIP hardening, upload limits.

## If something goes wrong live
- "Cannot reach the backend": backend stopped. Restart uvicorn and re-upload (uploads live in memory).
- Rate limit message: wait a minute. Use cached overview (reload doesn't re-call the model within a session).
- Slow response: say "Gemma is reading the repo" and keep talking; first calls take 10-30 seconds.
- Have screenshots of a good run saved as a backup.

## Final submission checklist
- [ ] README renders correctly on GitHub
- [ ] No secrets in git history (`git log -p | grep -i "AIza"` prints nothing); if a key was ever committed, revoke it and make a new one
- [ ] `python3 -m pytest` passes
- [ ] Works from a fresh clone following only the README steps
