import asyncio
import base64
import json
import os
import uuid
from typing import Dict, List, Optional, Any

from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler

# ADK agent imports
from google.adk.agents.llm_agent import LlmAgent
from tachyon_adk_client import TachyonAdkClient

# Load environment variables
load_dotenv()

IAM_EVIDENCE_DEBUG = os.getenv("IAM_EVIDENCE_DEBUG", "false").lower() == "true"

# Logger setup
LOG_DIR = os.getenv("IAM_EVIDENCE_LOG_DIR", "logs")
LOG_FILE = os.path.join(LOG_DIR, os.getenv("IAM_EVIDENCE_LOG_FILE", "iam_evidence.log"))
os.makedirs(LOG_DIR, exist_ok=True)
logger = logging.getLogger("iam_evidence")
if not logger.handlers:
    logger.setLevel(logging.DEBUG if IAM_EVIDENCE_DEBUG else logging.INFO)
    handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

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
    except Exception as e:
        logger.warning("Failed to read system instruction file: %s", e)
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
    except Exception as e:
        logger.warning("Mongo fetch failed: %s", e)
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
            except Exception as e:
                logger.debug("Inline payload decode failed: %s", e)
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
    except Exception as e:
        logger.debug("Model text not JSON: %s", e)
        return {
            "Answer": s,
            "Quality": "N/A",
            "Source": "",
            "Summary": "",
            "Reference": ""
        }

# Tools exposed to the LLM

def get_system_instruction(appId: str, controlId: str) -> str:  # noqa: N802
    """Return the resolved system instruction text for this app/control."""
    txt = resolve_system_instruction(appId, controlId)
    if not txt:
        raise ValueError("System instruction not found for the given appId/controlId")
    if IAM_EVIDENCE_DEBUG:
        logger.debug("Loaded system instruction len=%s for appId=%s controlId=%s", len(txt), appId, controlId)
    return txt

def validate_and_list_evidences(evidences: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate evidence objects and return cleaned list and names."""
    cleaned = validate_evidences(evidences)
    names = [e["fileName"] for e in cleaned]
    if IAM_EVIDENCE_DEBUG:
        logger.debug("Validated evidences: names=%s", names)
    return {"cleaned": cleaned, "evidenceNames": names}

# JSON-string variants to avoid missing-args tool call issues

def validate_and_list_evidences_json(evidences_json: str) -> Dict[str, Any]:
    """Accept evidences as JSON string to reduce tool arg shape errors."""
    try:
        parsed = json.loads(evidences_json) if evidences_json else []
    except Exception as e:
        raise ValueError(f"Invalid evidences_json: {e}")
    if not isinstance(parsed, list):
        raise ValueError("evidences_json must be a JSON array")
    return validate_and_list_evidences(parsed)

def iam_evidence_result(Answer: str, Quality: str, Source: str, Summary: str, Reference: str) -> Dict[str, str]:
    """Final structured result to be emitted as a functionResponse."""
    return {
        "Answer": Answer,
        "Quality": Quality,
        "Source": Source,
        "Summary": Summary,
        "Reference": Reference,
    }

def iam_evidence_result_json(payload_json: str) -> Dict[str, str]:
    """JSON-string variant to avoid missing-args failures from tool calls."""
    try:
        payload = json.loads(payload_json or "{}")
    except Exception as e:
        raise ValueError(f"Invalid payload_json: {e}")
    for key in ["Answer", "Quality", "Source", "Summary", "Reference"]:
        if key not in payload:
            payload.setdefault(key, "")
    return {
        "Answer": str(payload.get("Answer", "")),
        "Quality": str(payload.get("Quality", "")),
        "Source": str(payload.get("Source", "")),
        "Summary": str(payload.get("Summary", "")),
        "Reference": str(payload.get("Reference", "")),
    }

# Optional debug tool

def debug_dump(message: str) -> str:
    if IAM_EVIDENCE_DEBUG:
        logger.debug("%s", message)
    return "ok"

# Create the IAM Evidence Agent
def create_iam_evidence_agent():
    """Create the IAM Evidence evaluation agent using LlmAgent + TachyonAdkClient."""
    # Validate required env like hello_tachyon
    required_vars = ['MODEL', 'API_KEY', 'BASE_URL', 'USE_CASE_ID', 'UUID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.warning("Missing environment variables: %s", missing_vars)
        logger.warning("Please check your .env file and ensure all required variables are set.")

    model = TachyonAdkClient(
        model_name=f"openai/{os.getenv('MODEL', os.getenv('LLM_MODEL_ID', 'gemini-2.0-flash'))}",
        base_url=os.getenv('BASE_URL'),
        api_key=os.getenv('API_KEY'),
        use_case_id=os.getenv('USE_CASE_ID'),
        uuid=os.getenv('UUID'),
    )

    instruction_text = (
        "You are an IAM compliance expert. Follow these steps strictly:"
        "\n1) The user provides a JSON payload as inline data with fields appId, controlId, evidences[]."
        "\n2) Read that JSON and extract appId, controlId, and evidences."
        "\n3) Call get_system_instruction(appId, controlId) to retrieve the system instruction text."
        "\n4) EITHER (a) call validate_and_list_evidences(evidences) with a proper array argument,"
        " OR (b) call validate_and_list_evidences_json(JSON.stringify(evidences)) to avoid shape errors."
        "\n5) Using the retrieved system instruction and validated input, produce the final assessment by calling"
        " iam_evidence_result with explicit arguments OR iam_evidence_result_json(JSON.stringify({...}))."
        "\nRules: Always pass explicit, non-empty arguments. Do not emit a function call with missing args."
        " Prefer a single functionResponse and no extra commentary."
    )

    agent = LlmAgent(
        model=model,
        name=os.getenv("ROOT_AGENT_NAME", "iam_evidence_agent"),
        description="Evaluates IAM compliance evidence using dynamic system instructions and returns structured results.",
        instruction=instruction_text,
        tools=[
            get_system_instruction,
            validate_and_list_evidences,
            validate_and_list_evidences_json,
            iam_evidence_result,
            iam_evidence_result_json,
            debug_dump,
        ],
    )

    if IAM_EVIDENCE_DEBUG:
        logger.debug("Agent initialized")
        logger.debug("Instruction length: %s", len(instruction_text))
        logger.debug("Tools registered: get_system_instruction, validate_and_list_evidences, "
                     "validate_and_list_evidences_json, iam_evidence_result, iam_evidence_result_json, debug_dump")

    return agent

# Expose root_agent for ADK
root_agent = create_iam_evidence_agent()
