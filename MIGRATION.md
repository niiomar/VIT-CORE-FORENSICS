# Migration Guide — Restructuring to `backend/` + `frontend/`

Follow these steps **in order**. Do this on a new git branch so you can
bail out cleanly if something breaks.

```bash
git checkout -b restructure
```

## Step 1 — Move existing Python files into `backend/`

From your repo root:

```bash
mkdir -p backend
git mv main.py backend/main.py
git mv model.py backend/model.py
git mv requirements.txt backend/requirements.txt
```

## Step 2 — Move the model weights

```bash
mkdir -p backend/weights
git mv vitcore_best.pth backend/weights/vitcore_best.pth
```

> If `vitcore_best.pth` is large and not actually committed (just listed as
> "download required" in your README), skip this — just create the empty
> `backend/weights/` folder and drop the downloaded file there manually.

## Step 3 — Move the Vite build output

```bash
git mv static backend/static
```

## Step 4 — Extract this zip on top of your repo

This zip already contains the new files in the correct locations:

```bash
unzip -o vit-core-forensics-restructure.zip -d .
```

This adds/overwrites:
- `backend/auth.py` (new)
- `backend/audit.py` (new)
- `backend/main.py` (updated — replaces the one you just moved in Step 1)
- `backend/model.py` (updated — replaces the one you just moved in Step 1)
- `backend/.env.example` (new)
- `backend/tests/test_smoke.py` (new)
- `frontend/.env.example` (new)
- `frontend/src/app.js` (new — entry point)
- `frontend/src/components/sidebar.js` (new)
- `frontend/src/components/workspace.js` (new)
- `frontend/src/utils/api.js` (updated)
- `.gitignore` (updated)
- `Dockerfile` (new)
- `docker-compose.yml` (new)
- `MODEL_CARD.md` (new)
- `.github/workflows/ci.yml` (new)

## Step 5 — Update `frontend/src/index.html` (or wherever the script tag is)

Find:
```html
<script type="module" src="/src/main.js"></script>
```
Change to:
```html
<script type="module" src="/src/app.js"></script>
```

If `main.js` still exists and you don't need it, delete it:
```bash
git rm frontend/src/main.js
```

## Step 6 — Update `frontend/vite.config.js`

Add/update the build output directory so Vite builds straight into
`backend/static`:

```js
export default {
  build: {
    outDir: '../backend/static',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
};
```

## Step 7 — Set up env files

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Edit `backend/.env` and `frontend/.env` so `API_KEY` matches `VITE_API_KEY`.

## Step 8 — Remove tracked build artifacts / node_modules

If these were previously committed:

```bash
git rm -r --cached frontend/node_modules
git rm -r --cached backend/static
# re-add static with just the gitkeep so the folder exists
git add backend/static/.gitkeep
```

## Step 9 — Build and run

**Local dev (two terminals):**
```bash
# Terminal 1
cd backend && uvicorn main:app --reload --port 8000

# Terminal 2
cd frontend && npm install && npm run dev
```

**Production (single command):**
```bash
docker compose up --build
```

## Step 10 — Verify

```bash
curl http://localhost:8000/health
```

Should return `{"status": "ok", "version": "2.0.0"}`.

Then open the app in a browser, upload a test image, and confirm the
verdict + attention heatmap render correctly.

## Step 11 — Commit

```bash
git add .
git commit -m "Restructure into backend/ and frontend/, add auth, audit log, Docker, CI"
git push origin restructure
```

Open a PR, review the diff (it'll be large due to the file moves, but `git
mv` preserves history so the diff for moved files should show as renames,
not full add/delete pairs), then merge.
