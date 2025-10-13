# NHA Evidence Frontend (React + TypeScript)

A minimal React + Vite app to talk to the IAM Evidence agent. You can point it to:
- A2A agent server (recommended for end-to-end evidence flow)
- ADK Web/API server

## Prerequisites
- Node.js >= 18
- Backend running (pick ONE):
  - A2A IAM Evidence server: `python -m agents.iam_evidence` (default `http://127.0.0.1:8003`)
  - OR ADK Web/API server: `adk web .` (default `http://127.0.0.1:8000`)
- Backend env (examples):
```
# LLM/Tachyon
MODEL=gemini-2.0-flash
API_KEY=xxxxx
BASE_URL=http://localhost:7000
USE_CASE_ID=xxxxx
UUID=xxxxx
ROOT_AGENT_NAME=iam_evidence_agent

# System instruction and Mongo (optional)
SYSTEM_INSTRUCTION_FILE=./config/iam_system_instruction.txt
USE_MONGO=true
MONGO_URI=mongodb://localhost:27017
MONGO_DB=iam_eval
MONGO_SYSTEM_COLLECTION=system_instructions
```

## Configure frontend
Create `nha-frontend/.env.local` and set target:

- A2A (port 8003):
```
VITE_AGENT_URL=http://127.0.0.1:8003/run
VITE_APP_NAME=iam_evidence
```

- ADK Web/API (port 8000):
```
VITE_AGENT_URL=http://127.0.0.1:8000/run
VITE_APP_NAME=iam_evidence
```

If you hit CORS with ADK Web/API, enable Vite proxy:
```
VITE_USE_PROXY=true
VITE_AGENT_PROXY_TARGET=http://127.0.0.1:8000
```
Then you may set `VITE_AGENT_URL=/run` or keep the full URL; the proxy will forward `/run`.

## Run
```
cd nha-frontend
npm install
npm run dev
```
Open the printed URL (e.g., `http://localhost:5173`).

## How it works
- The UI gathers `appId`, `controlId`, and uploaded evidences (`fileName`, `mimeType`, `base64`).
- It builds inline JSON `{ appId, controlId, evidences }`, Base64-encodes it, and sends POST `/run` with:
```
{
  "app_name": "iam_evidence",
  "user_id": "<user>",
  "session_id": "<session>",
  "new_message": {
    "role": "user",
    "parts": [
      { "text": "Evaluate IAM evidence for control <id>" },
      { "inlineData": { "mimeType": "application/json", "data": "<base64 JSON>" } }
    ]
  }
}
```
- The IAM agent (LlmAgent + TachyonAdkClient) now:
  - Reads inlineData, fetches system instruction (file-first then Mongo via tools), validates evidences, and emits a functionResponse `iam_evidence_result` with fields `{ Answer, Quality, Source, Summary, Reference }`.
- The React app parses that functionResponse and renders the JSON.

## Validate
1) Backend: ensure it’s running with required env. For Mongo, set `USE_MONGO=true` and insert your system instruction for `(appId, controlId)`.
2) Frontend: upload a small text file, set `App ID` and `Control ID`, click "Evaluate IAM Evidence".
3) You should see the structured JSON result in the page.

## Troubleshooting
- No response / network error: verify `VITE_AGENT_URL` and backend port.
- CORS error (ADK Web/API): enable proxy (`VITE_USE_PROXY=true`, `VITE_AGENT_PROXY_TARGET=http://127.0.0.1:8000`) and restart `npm run dev`.
- Missing fields in result: ensure backend’s system instruction exists (file or Mongo) and that evidences are correctly encoded.
- Auth/endpoint errors: check `MODEL`, `API_KEY`, `BASE_URL`, `USE_CASE_ID`, `UUID` in backend `.env`.
