# Running and deploying WorkTwin

Three stages, each one works on its own:

1. **Local, mock mode** (no keys): 5 minutes. Use this to check everything runs.
2. **Local with Gemini**: add one API key, the twins really talk.
3. **Google Cloud**: Cloud Run + Firestore + Firebase Hosting, for the submission.

Commands are for macOS/Linux. On Windows use PowerShell and swap `. .venv/bin/activate` for `.venv\Scripts\Activate.ps1`.

## What you need installed

- Python 3.11 or newer, Node.js 20 or newer
- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) (`gcloud`)
- Firebase CLI: `npm install -g firebase-tools`

---

## 1. Local, mock mode

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

Open http://localhost:8080/health. You should see `"mock": true`.

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 and click **Try the demo team**, then: **Build twins → Open the twin room → Start the twins' meeting → Open retro (week 3) → Play Wrapped**.

Run the tests any time: `cd backend && pip install pytest && python -m pytest -q`.

## 2. Local with Gemini

1. Get a key at https://aistudio.google.com/apikey.
2. `cd backend && cp .env.example .env` and set `GEMINI_API_KEY=` to your key.
3. Restart uvicorn. `/health` should now show `"mock": false, "runtime": "adk"`.

If ADK ever misbehaves, set `AGENT_RUNTIME=genai` in `.env` to call Gemini directly. The code already falls back automatically per call.

**Optional, real data:**

- **GitHub:** create a fine-grained token (read-only: Contents, Pull requests, Metadata) and set `GITHUB_TOKEN`. Put the repo as `owner/repo` when creating the team, and each member's GitHub username when they join.
- **Google Drive (local):** `gcloud auth application-default login --scopes=https://www.googleapis.com/auth/drive.readonly,https://www.googleapis.com/auth/cloud-platform`, then paste the team folder link when creating the team. Members must join with the Google email they edit with.

**ADK dev UI (good deck screenshot):** from `backend/`, run `adk web adk_agents` and open the URL it prints. Pick `worktwin`.

## 3. Google Cloud

Replace `YOUR_PROJECT` with your project ID. Region `asia-southeast1` is Singapore, closest to KL.

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  firestore.googleapis.com secretmanager.googleapis.com drive.googleapis.com cloudscheduler.googleapis.com
gcloud firestore databases create --location=asia-southeast1
```

### Secrets

```bash
printf '%s' 'YOUR_GEMINI_KEY'   | gcloud secrets create gemini-api-key --data-file=-
printf '%s' 'YOUR_GITHUB_TOKEN' | gcloud secrets create github-token   --data-file=-
printf '%s' "$(openssl rand -hex 16)" | gcloud secrets create tapin-token --data-file=-

PROJECT_NUMBER=$(gcloud projects describe YOUR_PROJECT --format='value(projectNumber)')
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
gcloud projects add-iam-policy-binding YOUR_PROJECT --member="serviceAccount:$SA" --role=roles/secretmanager.secretAccessor
gcloud projects add-iam-policy-binding YOUR_PROJECT --member="serviceAccount:$SA" --role=roles/datastore.user
```

No GitHub token? Skip that secret and drop `GITHUB_TOKEN=...` from the deploy command below.

### Backend on Cloud Run

```bash
gcloud run deploy worktwin-api --source backend --region asia-southeast1 --allow-unauthenticated \
  --timeout 300 \
  --set-env-vars STORE=firestore,AGENT_RUNTIME=adk,GEMINI_MODEL=gemini-2.5-flash,CORS_ORIGINS=* \
  --set-secrets GEMINI_API_KEY=gemini-api-key:latest,GITHUB_TOKEN=github-token:latest,TAPIN_DEVICE_TOKEN=tapin-token:latest
```

It prints a URL like `https://worktwin-api-xxxxx.asia-southeast1.run.app`. Check `<URL>/health`.

### Frontend on Firebase Hosting

```bash
firebase login
firebase projects:addfirebase YOUR_PROJECT     # once, if the project isn't a Firebase project yet
cd frontend
echo "NEXT_PUBLIC_API_URL=https://worktwin-api-xxxxx.asia-southeast1.run.app" > .env.production
npm run build
firebase use --add YOUR_PROJECT
firebase deploy --only hosting
```

Then lock CORS to your site:

```bash
gcloud run services update worktwin-api --region asia-southeast1 \
  --update-env-vars CORS_ORIGINS=https://YOUR_PROJECT.web.app
```

### Google Drive on Cloud Run

Share the team's Drive folder (Viewer) with the service account email from `$SA` above. Then paste the folder link when creating the team, and press **Pull activity**.

### Weekly retro on a schedule (final round)

```bash
gcloud scheduler jobs create http worktwin-weekly-retro --location=asia-southeast1 \
  --schedule="0 21 * * 0" --time-zone=Asia/Kuala_Lumpur --http-method=POST \
  --uri="https://worktwin-api-xxxxx.asia-southeast1.run.app/teams/YOUR_TEAM_ID/retro"
```

### ESP32 tap-in

Open `iot/tapin_esp32/tapin_esp32.ino` in the Arduino IDE, install the **MFRC522** and **ArduinoJson** libraries, fill in Wi-Fi, the Cloud Run URL + `/tapin`, the team ID and the token (`gcloud secrets versions access latest --secret=tapin-token`). Tap an unknown card once; the team page then offers to link it to a member.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Frontend says it can't reach the server | Check `NEXT_PUBLIC_API_URL`, rebuild the frontend, and check CORS_ORIGINS |
| `/health` says `"mock": true` on Cloud Run | The `gemini-api-key` secret isn't attached; rerun the deploy command |
| Twin room stops mid-way | Check Cloud Run logs: `gcloud run services logs read worktwin-api --region asia-southeast1` |
| Drive pull says 403 insufficient scopes | Make sure `drive.googleapis.com` is enabled and the folder is shared with the service account |
| Model replies are slow | Use a Flash model; the meeting makes about 17 model calls |
| Demo must not fail on stage | Set `MOCK_LLM=true` on Cloud Run as a backup revision |
