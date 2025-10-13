# Hello Tachyon - Validation via ADK Web/API Server

This guide shows how to validate the minimal `hello_tachyon` agent end-to-end using the ADK Web/API server.

## Prerequisites
- Python and your existing ADK Web/API Server setup (same as other apps in this repo)
- `.env` in the repo root with these variables:
```
MODEL=gemini-2.0-flash
API_KEY=<your-api-key>
BASE_URL=http://localhost:7000
USE_CASE_ID=<your-use-case-id>
UUID=<your-uuid>
ROOT_AGENT_NAME=Compliance_Assistant
```

## Start ADK Web/API Server
- Use the same command you already use in this repo (examples):
```
# Option A: from repo root, ADK discovers agents/*/agent.py
adk web .

# Option B: from the agent directory
cd agents/hello_tachyon
adk web .
```
- Open the printed URL (default `http://127.0.0.1:8000`).

## Create a Session (API)
- Replace `USER_ID`/`SESSION_ID` as needed.
```
curl -s -X POST "http://127.0.0.1:8000/apps/hello_tachyon/users/test/sessions/s1" \
  -H "Content-Type: application/json" \
  -d '{}'
```

## Run a Message (API)
- Minimal text request:
```
curl -s -X POST "http://127.0.0.1:8000/run" \
  -H "Content-Type: application/json" \
  -d '{
    "app_name": "hello_tachyon",
    "user_id": "test",
    "session_id": "s1",
    "new_message": {
      "role": "user",
      "parts": [ { "text": "Ping Tachyon and summarize" } ]
    }
  }'
```
- You will receive an array of ADK events. Extract text parts:
```
# Requires jq
curl -s -X POST "http://127.0.0.1:8000/run" \
  -H "Content-Type: application/json" \
  -d '{
    "app_name": "hello_tachyon",
    "user_id": "test",
    "session_id": "s1",
    "new_message": {"role": "user", "parts": [ {"text": "status?"} ] }
  }' | jq -r '.[] | .content.parts[]? | .text? // empty'
```
- Expected output shape (two lines):
  1) One short human-readable sentence.
  2) A JSON object exactly with keys:
```
{
  "ok": true,
  "tachyon": { "baseUrl": "http://localhost:7000", "status": "reachable" },
  "echo": "status?",
  "summary": "<one short sentence summary>"
}
```
- If Tachyon is not reachable or returns an error, expect `ok: false` and `status: "unreachable"`.

## Validate via ADK Web UI
- Open `http://127.0.0.1:8000` and choose the `hello_tachyon` agent.
- Send a prompt like: `Ping Tachyon and summarize`.
- In the right panel, look for the assistant message that includes the short sentence and the JSON object on the next line.

## Troubleshooting
- No root_agent found:
  - Ensure `agents/hello_tachyon/agent.py` exists and defines `root_agent`.
  - Ensure `agents/` and `agents/hello_tachyon/` contain `__init__.py`.
- Import error for `tachyon_adk_client`:
  - Install or make sure it’s on the Python path in your environment.
- Missing environment variables:
  - Check `.env` matches the Prerequisites section; restart the server after changes.
- Port conflicts:
  - Stop the process using port 8000 or run ADK Web on a different port (check your ADK command options).
- Authentication/endpoint issues with Tachyon:
  - Verify `BASE_URL`, `API_KEY`, and any gateway/proxy settings in your environment.
