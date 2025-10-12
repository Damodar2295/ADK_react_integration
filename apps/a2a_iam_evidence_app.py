import streamlit as st
import base64
import json
import requests
import uuid
import os

# Config
AGENT_URL = os.getenv("IAM_EVIDENCE_A2A_URL", "http://localhost:8003/run")
APP_NAME = "iam_evidence"

st.set_page_config(page_title="IAM Evidence Chat Agent", page_icon="🛡️", layout="centered")
st.title("🛡️ IAM Evidence Chat Agent")

# Session State
if "user_id" not in st.session_state:
    st.session_state.user_id = f"user-{uuid.uuid4()}"
if "session_id" not in st.session_state:
    st.session_state.session_id = f"sess-{uuid.uuid4()}"

st.sidebar.header("Session")
st.sidebar.write(f"User ID: {st.session_state.user_id}")
st.sidebar.write(f"Session ID: {st.session_state.session_id}")

# Inputs
app_id = st.text_input("App ID", "APP_001")
control_id = st.text_input("Control ID", "CID_123")

uploaded_files = st.file_uploader(
    "Upload evidence files (PDF / images / docs)", accept_multiple_files=True
)

def to_base64(b: bytes) -> str:
    return base64.b64encode(b).decode("utf-8")

def build_inline_b64(evidences):
    inline_json = {
        "appId": app_id,
        "controlId": control_id,
        "evidences": evidences,
    }
    return base64.b64encode(json.dumps(inline_json).encode("utf-8")).decode("utf-8")

def send_request(inline_b64: str):
    payload = {
        "app_name": APP_NAME,
        "user_id": st.session_state.user_id,
        "session_id": st.session_state.session_id,
        "new_message": {
            "role": "user",
            "parts": [
                {"text": f"Evaluate IAM evidence for control {control_id}"},
                {"inlineData": {"mimeType": "application/json", "data": inline_b64}},
            ],
        },
    }
    resp = requests.post(AGENT_URL, json=payload, headers={"Content-Type": "application/json"}, timeout=60)
    resp.raise_for_status()
    return resp.json()

def parse_response(resp):
    # Expect an array of events
    if not isinstance(resp, list):
        return None
    for evt in resp:
        parts = (evt.get("content") or {}).get("parts") or []
        for p in parts:
            fr = p.get("functionResponse")
            if fr and fr.get("name") == "iam_evidence_result":
                return fr.get("response", {}).get("result")
            if p.get("text"):
                try:
                    return json.loads(p["text"])  # fallback: JSON-in-text
                except Exception:
                    pass
    return None

if st.button("🚀 Evaluate IAM Evidence"):
    evidences = []
    if uploaded_files:
        for f in uploaded_files:
            data = f.read()
            evidences.append(
                {
                    "fileName": f.name,
                    "mimeType": f.type or "application/octet-stream",
                    "base64": to_base64(data),
                }
            )
    try:
        inline_b64 = build_inline_b64(evidences)
        with st.spinner("Contacting IAM Evidence Agent..."):
            resp = send_request(inline_b64)
        result = parse_response(resp)
        if result:
            st.subheader("Result")
            st.json(result)
            # Optional audio support if present
            audio_url = result.get("audio_url") if isinstance(result, dict) else None
            if isinstance(audio_url, str) and audio_url:
                st.audio(audio_url)
        else:
            st.warning("No structured result found. Full response:")
            st.json(resp)
    except Exception as e:
        st.error(f"Request failed: {e}")
