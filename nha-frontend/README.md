# NHA Evidence Frontend (React + TypeScript)

A minimal React + Vite app to talk to the IAM Evidence A2A agent running on http://127.0.0.1:8003.

## Setup

```
cd nha-frontend
npm install
```

Optional: create `.env.local` with:

```
VITE_AGENT_URL=http://127.0.0.1:8003/run
VITE_APP_NAME=iam_evidence
```

## Run

Start the backend in another terminal:

```
python -m agents.iam_evidence
```

Start the frontend dev server:

```
npm run dev
```

Open the printed URL (default http://localhost:5173).

Upload evidence files, set App ID and Control ID, and click "Evaluate IAM Evidence".
