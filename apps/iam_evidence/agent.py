import os
import sys
import logging
import base64
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any

from dotenv import load_dotenv
import json
from google.adk.tools.tool_context import ToolContext  # ADK Artifacts API
from google.genai import types  # Part/Content if needed by stack
import pandas as pd
import io
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.function_tool import FunctionTool
from tachyon_adk_client import TachyonAdkClient

# Load environment variables (prefer local .env in this package)
from pathlib import Path as _Path
_env_path = _Path(__file__).parent / '.env'
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path, override=True)
else:
    load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import direct tools - try relative first, then absolute
try:
    from .database_tools import DatabaseTools
    from .jira_tools import JiraTools
    from .mongodb_tools import MongoDBTools
except ImportError:
    from database_tools import DatabaseTools
    from jira_tools import JiraTools
    from mongodb_tools import MongoDBTools


class NHAComplianceAgent:
    """Non-MCP NHA Compliance Agent using direct tools with LLM-driven delegation"""

    def __init__(self):
        # Initialize tool instances
        mongo_tools_instance = MongoDBTools()

        # Core tools (Mongo-only, as validation is evidence-driven and DB is not required)
        self.tools = [
            FunctionTool(mongo_tools_instance.get_system_instructions),
            FunctionTool(mongo_tools_instance.analyze_evidence_files),
            FunctionTool(mongo_tools_instance.store_compliance_report),
        ]

        # Add local file ingestion tool so agents can load uploaded evidence
        # Prefer ADK ToolContext variant (async) if already defined; fallback to instance method
        _tc_loader = globals().get('load_uploaded_evidence')
        if _tc_loader:
            self.tools.append(FunctionTool(_tc_loader))
        else:
            logger.warning("ToolContext load_uploaded_evidence not yet defined; using instance loader fallback")
            self.tools.append(FunctionTool(self.load_uploaded_evidence))
        # Add native chat upload ingestion tool (accepts files from ADK Web UI)
        self.tools.append(FunctionTool(self.ingest_uploaded_evidence))

        self.mongo_tools = mongo_tools_instance
        self._setup_environment()
        # Build a dynamic pool of control-specific sub agents (empty at boot; created on-demand)
        self.control_agents = {}
        # Map original control_id -> sanitized agent_name
        self.control_agent_name_map = {}
        # In-memory evidence cache: id -> { filename, content }
        self._evidence_cache: Dict[str, Dict[str, Any]] = {}
        # Create the coordinator agent
        self._create_agent()

    def _setup_environment(self):
        """Setup environment variables for optimal performance"""
        # Set optimal configuration
        os.environ.setdefault('SCHEMA_SOURCE', 'db')
        os.environ.setdefault('TEXT_TO_SQL_FAST_MODE', 'true')
        os.environ.setdefault('DEBUG_MODE', 'false')

        # Configure supported file types for comprehensive document processing
        default_extensions = 'pdf,doc,docx,txt,rtf,xlsx,xls,csv,jpg,jpeg,png,tiff,bmp,ppt,pptx,html,xml,json'
        os.environ.setdefault('ALLOWED_FILE_EXTENSIONS', default_extensions)
        print(f"[INFO] Supported file extensions: {os.getenv('ALLOWED_FILE_EXTENSIONS')}")

        # Local uploads directory
        os.environ.setdefault('EVIDENCE_UPLOADS_DIR', 'uploads')

    def _print_config(self):
        """Print configuration for debugging"""
        print(f"[INFO] Initializing NHA Compliance System (Non-MCP Version)")
        print(f"[CONFIG] Model: {os.getenv('MODEL', 'Not Set')}")
        print(f"[CONFIG] Agent: {os.getenv('ROOT_AGENT_NAME', 'NHA_Compliance_Assistant')}")
        print(f"[CONFIG] Database: Disabled in Non-MCP agent")
        print(f"[CONFIG] MongoDB DB: {os.getenv('MONGODB_DATABASE', 'Not Set')}")
        print(f"[CONFIG] Prompt Collection: {os.getenv('MONGODB_SYSTEM_INSTRUCTIONS_COLLECTION', 'prompt')}")

    def _create_agent(self):
        """Create the coordinator LLM agent that delegates via transfer_to_agent."""
        coordinator_name = os.getenv('ROOT_AGENT_NAME', 'NHA_Coordinator')
        self.agent = LlmAgent(
            model=TachyonAdkClient(model_name=f"openai/{os.getenv('MODEL', 'gemini-2.0-flash')}",),
            name=coordinator_name,
            description="Coordinator that routes each control to its specialized sub-agent via LLM-driven transfer.",
            instruction=(
                "You are the coordinator for NHA evidence validation.\n\n"
                "First, collect all inputs in one turn: pairs of (control_id, app_name) and a list of evidence files.\n"
                "Users may provide multiple controls.\n"
                "Immediately call the tool ensure_control_agents with the list of control_ids provided to dynamically prepare sub-agents.\n"
                "For each (control_id, app_name), transfer_to_agent(agent_name from the mapping returned by ensure_control_agents)\n"
                "Sub-agent behavior: fetch system instructions from MongoDB with prompt_name equal to the control_id; select and analyze only relevant files; then synthesize a final combined compliance report across the provided controls and apps.\n"
                "After all sub-agents finish, synthesize the final combined compliance report across the provided controls and apps.\n"
                "Rules: Do not ask for confirmations between steps. Proceed autonomously after the initial data collection. Prefer short responses."
            ),
            tools=self.tools + [FunctionTool(self.ensure_control_agents), FunctionTool(self.analyze_evidence_by_ids)],
            sub_agents=[],
        )

    def _sanitize_agent_name(self, name: str) -> str:
        import re as _re
        s = _re.sub(r"[^0-9a-zA-Z_]+", "_", name)
        if s and s[0].isdigit():
            s = f"_{s}"
        return s

    def _create_control_agent(self, control_id: str) -> LlmAgent:
        """Create or return a specialized sub-agent for a specific control ID.
        Loads system instructions from MongoDB using the control_id as the prompt name.
        """
        # Check if agent already exists
        if control_id in self.control_agents:
            return self.control_agents[control_id]

        # Load system instructions from MongoDB
        prompt_name = control_id  # per requirement, use the control ID as the variable/prompt name
        system_instruction = self.mongo_tools.get_system_instructions(prompt_name)

        if not system_instruction:
            raise ValueError(f"No system instruction found for Control ID: {control_id}")

        # Create a new agent for the specific control
        control_agent = LlmAgent(
            model=TachyonAdkClient(model_name=f"openai/{os.getenv('MODEL', 'gemini-2.0-flash')}",),
            name=self._sanitize_agent_name(control_id),  # sanitized agent name for identifier rules
            description=f"Specialist for control {control_id}. Fetches its system instructions from MongoDB by prompt name '{control_id}'",
            instruction=(
                f"{system_instruction}\n\n"
                "Guidance:\n"
                "- The coordinator provides (control_id, app_name).\n"
                "- If the chat has uploaded files, call ingest_uploaded_evidence(files=<the ADK provided uploads>, app_name=<your assigned app_name>) to retrieve from cache.\n"
                "- If no files are available from chat, call load_uploaded_evidence(app_name=<your assigned app_name>) to retrieve from disk.\n"
                "- Select only evidence relevant to your assigned app_name using filenames/content.\n"
                "- Then call analyze_evidence_by_ids(file_ids=[ids of relevant files], system_instructions=this_control_instruction) to process.\n"
                "- Output a concise compliance report for this control and app, with findings and pass/fail per requirement."
            ),
            tools=self.tools + [FunctionTool(self.analyze_evidence_by_ids)],
        )

        # Store the created agent in the pool
        self.control_agents[control_id] = control_agent
        # Track mapping from original control_id to sanitized agent name
        self.control_agent_name_map[control_id] = control_agent.name

        # Attach to coordinator's sub_agents so AutoFlow can route transfer_to_agent
        if not any(a.name == control_agent.name for a in getattr(self.agent, 'sub_agents', [])):
            self.agent.sub_agents.append(control_agent)

        return control_agent

    # Tool: ensure_control_agents
    def ensure_control_agents(self, control_ids: List[str]) -> Dict[str, Dict[str, str]]:
        """Prepare sub-agents for the given control IDs and attach them for transfer routing.
        Returns mapping: control_id -> { status, agent_name, message? }.
        """
        results: Dict[str, Dict[str, str]] = {}
        for cid in control_ids:
            try:
                self._create_control_agent(cid)
                results[cid] = {
                    'status': 'ready',
                    'agent_name': self.control_agent_name_map.get(cid) or self._sanitize_agent_name(cid)
                }
            except Exception as e:
                results[cid] = {
                    'status': 'error',
                    'agent_name': self.control_agent_name_map.get(cid) or self._sanitize_agent_name(cid),
                    'message': str(e)
                }
        return results

    # Tool: load_uploaded_evidence
    def load_uploaded_evidence(self, app_name: Optional[str] = None, dir_path: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Load uploaded evidence files from a directory and cache contents to avoid token bloat.
        dir_path defaults to env EVIDENCE_UPLOADS_DIR or './uploads'.
        - If app_name is provided, only include files whose filename contains the app_name (case-insensitive).
        Returns: List of manifests { id, filename, size } (no content returned).
        """
        base_dir = Path(dir_path or os.getenv('EVIDENCE_UPLOADS_DIR', 'uploads'))
        if not base_dir.exists() or not base_dir.is_dir():
            logging.warning(f"[load_uploaded_evidence] Uploads directory not found: {base_dir}")
            return []

        allowed = set((os.getenv('ALLOWED_FILE_EXTENSIONS', '') or '').replace(' ', '').split(','))
        results: List[Dict[str, Any]] = []
        all_results: List[Dict[str, Any]] = []
        app_filter = (app_name or '').lower().strip()

        for fp in sorted(base_dir.glob('**/*')):
            if len(results) >= limit:
                break
            if not fp.is_file():
                continue
            ext = fp.suffix.lower().lstrip('.')
            if ext and ext not in allowed:
                continue

            try:
                content_bytes = fp.read_bytes()
                content = base64.b64encode(content_bytes).decode('ascii')
                evid = str(uuid.uuid4())
                self._evidence_cache[evid] = {'filename': fp.name, 'content': content}
                item = {'id': evid, 'filename': fp.name, 'size': len(content)}
                all_results.append(item)
                if not app_filter or app_filter in fp.name.lower():
                    results.append(item)
            except Exception as e:
                logging.warning(f"[load_uploaded_evidence] Failed to process file {fp}: {e}")

        if app_filter and not results:
            results = all_results[:limit]
        logging.info(f"[load_uploaded_evidence] Normalized {len(results)} of {len(all_results)} files")
        return results

    # Tool: ingest_uploaded_evidence
    def ingest_uploaded_evidence(self, files: Optional[List[Any]] = None, app_name: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Normalize evidence from native ADK Web chat uploads and cache contents.
        Accepts heterogeneous items (filename/name, content/text, data/base64/bytes, path/filepath, meta).
        Returns manifests { id, filename, size } only. Use analyze_evidence_by_ids to process.
        """
        if not files:
            logging.info("[ingest_uploaded_evidence] No files provided; returning empty list.")
            return []

        allowed = set((os.getenv('ALLOWED_FILE_EXTENSIONS', '') or '').replace(' ', '').split(','))
        app_filter = (app_name or '').lower().strip()
        results: List[Dict[str, Any]] = []
        all_results: List[Dict[str, Any]] = []

        def _normalize_one(item: Any) -> Optional[Dict[str, str]]:
            try:
                # Extract filename
                fname = None
                for key in ('filename', 'name', 'file_name'):
                    if isinstance(item, dict) and key in item:
                        fname = str(item[key])
                        break
                # Some ADK wrappers may store metadata under 'meta'
                meta = None
                if not fname and isinstance(item, dict) and isinstance(item.get('meta'), dict):
                    meta = item['meta']
                    for key in ('filename', 'file_name', 'name'):
                        if key in meta:
                            fname = str(meta[key])
                            break
                if not fname:
                    fname = 'uploaded_evidence'

                # Extract content
                content: Optional[str] = None

                # direct string content
                if isinstance(item, dict):
                    for key in ('content', 'text'):
                        if key in item and isinstance(item[key], str):
                            content = item[key]
                            break
                # base64 or bytes
                if content is None and isinstance(item, dict):
                    for key in ('data', 'base64', 'bytes'):
                        if key in item and item[key]:
                            data = item[key]
                            if isinstance(data, (bytes, bytearray)):
                                content = base64.b64encode(data).decode('ascii')
                            else:
                                # assume already base64-encoded string
                                content = str(data)
                            break
                # path on disk
                if content is None and isinstance(item, dict):
                    for key in ('path', 'filepath'):
                        if key in item and item[key]:
                            p = Path(item[key])
                            if p.exists() and p.is_file():
                                ext = p.suffix.lower().lstrip('.')
                                if ext and ext not in allowed:
                                    return None
                                content = base64.b64encode(p.read_bytes()).decode('ascii')
                            break

                if content is None:
                    return None

                evid_id = str(uuid.uuid4())
                self._evidence_cache[evid_id] = {'filename': fname, 'content': content}
                return {'id': evid_id, 'filename': fname, 'size': len(content)}
            except Exception as e:
                logging.warning(f"[ingest_uploaded_evidence] Failed to normalize item: {e}")
        return None

        for it in files[:limit]:
            norm = _normalize_one(it)
            if not norm:
                continue
            all_results.append(norm)
            if not app_filter or app_filter in norm['filename'].lower():
                results.append(norm)

        if app_filter and not results:
            results = all_results[:limit]
        logging.info(f"[ingest_uploaded_evidence] Normalized {len(results)} of {len(all_results)} uploaded items")
        return results

    # Tool: analyze_evidence_by_ids
    def analyze_evidence_by_ids(self, file_ids: List[str], system_instructions: Optional[str] = None) -> Dict[str, Any]:
        """Resolve evidence ids from cache and run analysis. Returns analysis dict.
        Use this instead of passing raw contents through the LLM to avoid token overflows.
        """
        files: List[Dict[str, Any]] = []
        for fid in file_ids:
            item = self._evidence_cache.get(fid)
            if item:
                files.append({'filename': item['filename'], 'content': item['content']})
            else:
                logging.warning(f"[analyze_evidence_by_ids] Missing file id: {fid}")
        return self.mongo_tools.analyze_evidence_files(files, system_instructions)

    def start(self):
        """Start the NHA Compliance Agent"""
        print("🚀 Starting NHA Compliance Assistant (Non-MCP, Multi-Agent Delegation)")
        print("Ready to route controls to specialized sub-agents and process evidence...")
        return self.agent


def main():
    """Main entry point"""
    try:
        # Initialize the NHA Compliance Agent
        nha_agent = NHAComplianceAgent()
        agent = nha_agent.start()

        print("\n" + "-"*60)
        print("🛡️  NHA COMPLIANCE ASSISTANT (NON-MCP VERSION) READY")
        print("-"*60)
        print("\nTo start validation, provide:")
        print("1. Control ID (required)")
        print("2. Application ID (required)")
        print("3. Jira Ticket ID (optional)")
        print("4. Evidence files (optional)")
        print("\nThe system will then execute the complete validation workflow automatically.")
        print("-"*60)

        return agent

    except Exception as e:
        logger.error(f"Failed to initialize NHA Compliance Agent: {e}")
        raise


# Create root_agent for ADK web server
try:
    root_agent = main()
except Exception as _e:
    # If initialization fails at import time, defer by creating a minimal placeholder agent
    # so the module import doesn't crash environments that introspect 'root_agent'.
    root_agent = LlmAgent(
        model=TachyonAdkClient(model_name=f"openai/{os.getenv('MODEL', 'gemini-2.0-flash')}",),
        name=os.getenv('ROOT_AGENT_NAME', 'NHA_Coordinator'),
        instruction=(
            "Initialization failed; please check server logs."
        ),
        tools=[],
    )
    # Removed stray top-level code that referenced undefined names and used 'return' at module scope.

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

# (Removed alternate LiteLLM-based agent to avoid unsupported content parts.)

# ==== ADK ToolContext-based helper constants and functions for artifact conversion ====

CSV_MIMES = {"text/csv"}
XLS_MIMES = {
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
CSV_EXTS = {".csv"}
XLS_EXTS = {".xls", ".xlsx"}

def _is_csv_or_excel(filename: str, mime_type: Optional[str]) -> bool:
    ext = (filename or "").lower().rsplit(".", 1)
    ext = f".{ext[-1]}" if len(ext) == 2 else ""
    mt = (mime_type or "").lower()
    return (ext in CSV_EXTS or ext in XLS_EXTS) or (mt in CSV_MIMES or mt in XLS_MIMES)

def _bytes_to_markdown_table(data: bytes, mime: str, name: str) -> str:
    """Convert CSV/XLSX bytes to a compact GitHub-flavored markdown table."""
    if mime in CSV_MIMES or name.lower().endswith(".csv"):
        df = pd.read_csv(io.BytesIO(data))
    else:
        df = pd.read_excel(io.BytesIO(data), sheet_name=0)
    return df.to_markdown(index=False)


# Existing signature must remain the same
async def load_uploaded_evidence(tool_context: ToolContext, filename: str) -> dict:  # type: ignore[override]
    """
    Existing behavior preserved.
    Added: if CSV/XLSX, convert to markdown and register as artifact; include in evidence_artifacts.
    Returns (backward-compatible) dict with 'evidence_artifacts' plus:
      - 'converted': bool
      - 'markdown_artifact': <name>.md.txt  (present only when converted)
    """
    try:
        part = await tool_context.load_artifact(filename)
        inline = getattr(part, "inline_data", None)
        mime = getattr(inline, "mime_type", "") or ""
        data = getattr(inline, "data", None)

        base_name = filename.rsplit("/", 1)[-1]
        evidence_artifacts: list[str] = [base_name]
        converted = False
        md_artifact_name: Optional[str] = None

        if _is_csv_or_excel(base_name, mime) and data:
            md_text = _bytes_to_markdown_table(data, mime, base_name)
            md_artifact_name = f"{base_name}.md.txt"
            await tool_context.save_artifact(
                name=md_artifact_name,
                data=md_text.encode("utf-8"),
                mime_type="text/markdown",
            )
            evidence_artifacts.append(md_artifact_name)
            converted = True
            logger.info(f"Converted '{base_name}' -> '{md_artifact_name}' via ToolContext.save_artifact")

        return {
            "status": "success",
            "evidence_artifacts": evidence_artifacts,
            "converted": converted,
            **({"markdown_artifact": md_artifact_name} if md_artifact_name else {}),
        }
    except Exception as e:
        logger.exception("load_uploaded_evidence failed: %s", e)
        return {"status": "error", "message": f"load_uploaded_evidence failed: {e}"}
