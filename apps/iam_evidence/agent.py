import asyncio
import base64
import json
import os
import uuid
from typing import Dict, List, Optional

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Optional MongoDB imports (only if USE_MONGO=true)
try:
    from pymongo import MongoClient
    MONGO_AVAILABLE = True
except ImportError:
    MONGO_AVAILABLE = False

# System instruction helpers
def load_system_instruction_from_file() -> Optional[str]:
    """Load system instruction from text file (primary source)."""
    path = os.getenv("SYSTEM_INSTRUCTION_FILE", "./config/iam_system_instruction.txt")
    try:
        with open(path, "r", encoding="utf-8") as f:
            txt = f.read().strip()
            return txt or None
    except Exception:
        return None

def fetch_system_instruction_from_mongo(app_id: str, control_id: str) -> Optional[str]:
    """Fetch system instruction from MongoDB (optional fallback)."""
    if os.getenv("USE_MONGO", "false").lower() != "true":
        return None

    if not MONGO_AVAILABLE:
        return None

    try:
        client = MongoClient(os.getenv("MONGO_URI"))
        db_name = os.getenv("MONGO_DB", "iam_eval")
        coll_name = os.getenv("MONGO_SYSTEM_COLLECTION", "system_instructions")
        doc = client[db_name][coll_name].find_one(
            {"appId": app_id, "controlId": control_id},
            {"systemInstruction": 1, "_id": 0}
        )
        return (doc or {}).get("systemInstruction")
    except Exception:
        return None

def resolve_system_instruction(app_id: str, control_id: str) -> Optional[str]:
    """Resolve system instruction: file first, then Mongo fallback."""
    # 1) Try text file first
    txt = load_system_instruction_from_file()
    if txt:
        return txt
    # 2) If enabled, fallback to Mongo
    return fetch_system_instruction_from_mongo(app_id, control_id)

# Evidence validation
def validate_evidences(evidences: List[Dict]) -> List[Dict]:
    """Validate evidence format and clean base64 data."""
    out = []
    for e in evidences or []:
        if not all(k in e for k in ("fileName", "mimeType", "base64")):
            raise ValueError(f"Invalid evidence format; expected fileName/mimeType/base64: {list(e.keys())}")

        b64 = e["base64"]
        if isinstance(b64, str) and "base64," in b64[:80]:
            b64 = b64.split("base64,", 1)[-1]

        out.append({
            "fileName": e["fileName"],
            "mimeType": e["mimeType"],
            "base64": b64
        })
    return out

# Inline payload decoder
def decode_inline_payload(parts: list) -> dict:
    """Decode inline JSON payload from /run parts[].inlineData."""
    for p in parts or []:
        inline = p.get("inlineData")
        if inline and inline.get("mimeType") == "application/json":
            try:
                raw = base64.b64decode(inline["data"]).decode("utf-8")
                return json.loads(raw)
            except Exception:
                continue
    return {}

# Robust JSON parsing
def parse_model_json(txt: str) -> dict:
    """Parse model output as JSON, with fallback to text."""
    s = (txt or "").strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:].strip()

    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else {"Answer": s}
    except Exception:
        return {
            "Answer": s,
            "Quality": "N/A",
            "Source": "",
            "Summary": "",
            "Reference": ""
        }

# Create the IAM Evidence Agent
def create_iam_evidence_agent():
    """Create the IAM Evidence evaluation agent."""
    # LLM configuration
    llm = LiteLlm(
        model="gemini-1.5-flash",
        api_key=os.environ.get("GOOGLE_API_KEY")
    )

    agent = Agent(
        name="iam_evidence_agent",
        description="Evaluates IAM compliance evidence and generates structured assessment reports.",
        model=llm,
        instruction="You are an IAM compliance expert. Analyze provided evidence and generate structured JSON reports according to the system guidelines.",
    )

    return agent

# Expose root_agent for ADK
root_agent = create_iam_evidence_agent()
