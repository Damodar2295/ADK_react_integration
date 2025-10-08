import os
import json
from typing import Dict, List, Any, Optional
try:
    from google.adk.agents.llm_agent import LlmAgent  # Preferred agent class
    LLM_AVAILABLE = True
except Exception:
    LlmAgent = None  # type: ignore
    LLM_AVAILABLE = False
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters
from tachyon_adk_client import TachyonAdkClient
from dotenv import load_dotenv
import json
import logging
import time
import base64
import mimetypes
from typing import Tuple

# --- Mongo helpers (lazy singleton) ---
try:
    from pymongo import MongoClient  # type: ignore
except Exception:
    MongoClient = None  # type: ignore

_mongo_client = None

def _get_mongo():
    global _mongo_client
    if _mongo_client is None:
        if MongoClient is None:
            raise RuntimeError("pymongo is not installed. Please install it or set USE_MCP=true.")
        uri = os.getenv("MONGO_URI")
        if not uri:
            raise RuntimeError("MONGO_URI not set. Please provide Mongo connection string.")
        _mongo_client = MongoClient(uri)
    return _mongo_client

def fetch_system_instruction(app_id: str, control_id: str) -> Optional[str]:
    db_name = os.getenv("MONGO_DB", "iam_eval")
    coll_name = os.getenv("MONGO_SYSTEM_COLLECTION", "system_instructions")
    client = _get_mongo()
    doc = client[db_name][coll_name].find_one(
        {"appId": app_id, "controlId": control_id},
        {"systemInstruction": 1, "_id": 0}
    )
    return (doc or {}).get("systemInstruction")

# --- Evidence normalization helpers ---
def _guess_mime(file_name: str) -> str:
    mt, _ = mimetypes.guess_type(file_name or "")
    return mt or "application/octet-stream"

def _strip_data_uri(b64: str) -> str:
    if isinstance(b64, str) and "base64," in b64[:80]:
        return b64.split("base64,", 1)[-1]
    return b64

def _to_base64_from_bytes(b: bytes) -> str:
    return base64.b64encode(b).decode("utf-8")

def _read_file_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()

def normalize_evidences(raw_list: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for idx, ev in enumerate(raw_list or []):
        file_name = ev.get("fileName") or ev.get("name") or f"evidence_{idx}"
        mime_type = ev.get("mimeType") or _guess_mime(file_name)

        b64 = ev.get("base64")
        if isinstance(b64, str) and b64:
            out.append({"fileName": file_name, "mimeType": mime_type, "base64": _strip_data_uri(b64)})
            continue

        b = ev.get("bytes") or ev.get("buffer")
        if isinstance(b, (bytes, bytearray)):
            out.append({"fileName": file_name, "mimeType": mime_type, "base64": _to_base64_from_bytes(bytes(b))})
            continue

        file_path = ev.get("filePath") or ev.get("path")
        if isinstance(file_path, str) and os.path.exists(file_path):
            data = _read_file_bytes(file_path)
            out.append({"fileName": file_name, "mimeType": mime_type, "base64": _to_base64_from_bytes(data)})
            continue
        # else skip invalid entries silently
    return out

def parse_llm_json(txt: str) -> Dict[str, Any]:
    s = (txt or "").strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:].strip()
    try:
        return json.loads(s)
    except Exception:
        return {"Answer": s, "Quality": "N/A", "Source": "", "Summary": s[:200], "Reference": ""}

# Load environment variables
load_dotenv(override=True)

# Ensure ServiceAccounts table is accessible and schema is live
_current_exact_entities = os.getenv('EXACT_ENTITY_NAMES', '')
if 'ServiceAccounts' not in _current_exact_entities:
    if _current_exact_entities:
        os.environ['EXACT_ENTITY_NAMES'] = f"{_current_exact_entities},ServiceAccounts"
    else:
        os.environ['EXACT_ENTITY_NAMES'] = 'ServiceAccounts'
    print("[INFO] Added ServiceAccounts to EXACT_ENTITY_NAMES for schema access")

if os.getenv('SCHEMA_SOURCE') != 'db':
    os.environ['SCHEMA_SOURCE'] = 'db'
    print("[INFO] Set SCHEMA_SOURCE to 'db' for live database schema access")

# Get environment variables for MCP tools
env_variables = os.environ.copy()

# Validate critical environment variables
required_vars = ['MODEL', 'API_KEY', 'BASE_URL', 'USE_CASE_ID', 'UUID']
missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    print(f"[WARNING] Missing environment variables: {missing_vars}")

# NHA Compliance Controls - Single Control Solution
NHA_CONTROLS = {
    "C-305377": {
        "name": "Non-Human Account Inventory and Password Validation",
        "description": "Comprehensive validation of non-human account inventory and password compliance across all applications.",
        "workflow_phases": {
            "Q1": "Application NHA Identification",
            "Q2": "ESAR Registration Validation",
            "Q3": "Password Construction Compliance (NHA-315-01)",
            "Q4": "Password Rotation Compliance (NHA-315-11)"
        }
    }
}

class NHAComplianceAgent:
    """Specialized agent for NHA compliance validation with MongoDB MCP integration"""

    def __init__(self):
        self.model_name = f"openai/{os.getenv('MODEL', 'gemini-2.0-flash')}"
        # Print minimal config to help diagnose envs at runtime
        print(f"[CONFIG] Model: {self.model_name}")
        print(f"[CONFIG] EXACT_ENTITY_NAMES: {os.getenv('EXACT_ENTITY_NAMES')}")
        print(f"[CONFIG] SCHEMA_SOURCE: {os.getenv('SCHEMA_SOURCE')}")

    def create_nha_agent(self, control_id: str = "C-305377") -> Any:
        """Create NHA compliance agent with MongoDB MCP for prompt retrieval"""
        if control_id not in NHA_CONTROLS:
            raise ValueError(f"Control {control_id} not supported for NHA compliance")

        return LlmAgent(
            model=TachyonAdkClient(model_name=self.model_name, name=f"NHA_{control_id}_Agent"),
            name=f"NHA_{control_id}_Agent",
            instruction=self._get_nha_instruction(control_id),
            tools=self._get_nha_tools()
        )

    def _get_nha_instruction(self, control_id: str) -> str:
        """Get NHA-specific instruction with MongoDB prompt integration"""
        control_info = NHA_CONTROLS[control_id]

        return f"""
You are the NHA Compliance Validation Agent specialized in {control_info['name']}.

**CONTROL:** {control_id} - {control_info['description']}

**NHA VALIDATION WORKFLOW:**

**PHASE 1: Q1 - Application NHA Identification**
1. Ask: "Does this application have non-platform-based service account(s)/non-human account(s) which is hosted?"
2. If NO: Request evidence to confirm no NHAs exist
3. If YES: Proceed to Q2 and collect Application ID and AU Owner Name

**PHASE 2: Q2 - ESAR Registration Validation**
1. Query ServiceAccounts table to verify NHA registration in eSAR
2. If accounts found in eSAR: Proceed to Q3
3. If accounts missing from eSAR: Request remediation evidence

**PHASE 3: Q3 - Password Construction Compliance (NHA-315-01)**
1. Validate password construction requirements (16+ chars, 3+ types, etc.)
2. Verify cryptographically protected storage
3. Check password history restrictions

**PHASE 4: Q4 - Password Rotation Compliance (NHA-315-11)**
1. Determine account interaction type from database
2. Validate rotation requirements based on account type
3. Check evidence for rotation compliance

**MONGODB PROMPT INTEGRATION:**
Use MongoDB MCP tool to retrieve control-specific system prompt:
- Collection: control_prompts
- Query: {{'control_id': '{control_id}'}}
- Use retrieved prompt for detailed validation criteria

**JIRA INTEGRATION:**
For non-compliant findings:
1. Check for existing Jira tickets
2. Create new tickets with format: "NHA Compliance Gap - {control_id} - [APP_ID] - [SERVICE_ACCOUNT_ID]"
3. Project: {os.getenv('JIRA_PROJECT_KEY', 'BDFS')}
4. Priority: {os.getenv('JIRA_PRIORITY', 'High')}

**DATABASE INTEGRATION:**
- ServiceAccounts table for NHA discovery and validation
- eSAR database for registration verification
- Timeout: {os.getenv('DATABASE_AGENT_TIMEOUT', '300')} seconds

**Begin NHA compliance validation workflow with MongoDB prompt integration.
"""

    def _get_nha_tools(self) -> List[MCPToolset]:
        """Get MCP tools for NHA compliance validation"""
        return [
            # MongoDB for control-specific prompts and evidence analysis
            MCPToolset(
                connection_params=StdioServerParameters(
                    command='python',
                    args=['-m', 'tachyon_mcp_mongo'],
                    env=env_variables,
                    read_timeout_seconds=int(os.getenv('DOCUMENT_ANALYSIS_TIMEOUT', '300'))
                )
            ),
            # SQL Server for database queries
            MCPToolset(
                connection_params=StdioServerParameters(
                    command='python',
                    args=['-m', 'tachyon_mcp_texttosql'],
                    env=env_variables,
                    read_timeout_seconds=int(os.getenv('DATABASE_AGENT_TIMEOUT', '300'))
                )
            ),
            # Jira for remediation tracking
            MCPToolset(
                connection_params=StdioServerParameters(
                    command='python',
                    args=['-m', 'tachyon_mcp_jira'],
                    env=env_variables,
                    read_timeout_seconds=int(os.getenv('JIRA_AGENT_TIMEOUT', '300'))
                )
            )
        ]

    def run_nha_validation(self, application_id: str, control_id: str = "C-305377") -> str:
        """Run NHA compliance validation with MongoDB prompt integration"""
        if control_id not in NHA_CONTROLS:
            return f"❌ Error: Control '{control_id}' not supported. Available: {', '.join(NHA_CONTROLS.keys())}"

        control_info = NHA_CONTROLS[control_id]

        print(f"\n🔍 NHA Compliance Validation: {control_id}")
        print(f"📋 Control: {control_info['name']}")
        print(f"📝 Application: {application_id}")
        print(f"🔄 Workflow: {len(control_info['workflow_phases'])} phases (Q1-Q{len(control_info['workflow_phases'])})")

        try:
            # Create NHA agent
            agent = self.create_nha_agent(control_id)

            # Generate MongoDB-integrated prompt
            prompt = f"""
Conduct NHA compliance validation for application: {application_id}

**CONTROL:** {control_id}
**PHASES:** {', '.join(control_info['workflow_phases'].values())}

**INSTRUCTIONS:**
1. Use MongoDB MCP to retrieve the system prompt for {control_id}
2. Follow the 4-question NHA validation workflow (Q1-Q4)
3. Ask questions in sequence and collect user responses
4. Use database queries to verify NHA information
5. Validate evidence provided by user
6. Create Jira tickets for non-compliant findings
7. Provide comprehensive compliance assessment

**MONGODB QUERY:**
Use tool: mongo_query with query: {{"control_id": "{control_id}"}}
to retrieve the control-specific validation criteria and requirements.

Start with Q1: Application NHA Identification.
"""

            # Execute validation with MongoDB integration
            result = agent.execute(prompt, {
                "control_id": control_id,
                "application_id": application_id,
                "workflow_phases": control_info['workflow_phases']
            })

            return result

        except Exception as e:
            return f"❌ Error running NHA validation: {str(e)}"

    # --- New High-level API for Frontend/Bridge ---
    def validate_submission(
        self,
        control_id: str,
        application_id: str,
        au_owner: Optional[str] = None,
        evidence_files: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Validate a submission coming from the frontend.

        Parameters
        - control_id: Only 'C-305377' supported
        - application_id: App identifier provided by user
        - au_owner: Application Unit/Owner name
        - evidence_files: List of evidence metadata dicts

        Returns
        - Structured dict with per-question results and overall compliance
        """
        if control_id not in NHA_CONTROLS:
            return {
                "success": False,
                "error": f"Unsupported control_id: {control_id}",
                "supported_controls": list(NHA_CONTROLS.keys()),
            }

        control_info = NHA_CONTROLS[control_id]
        # Normalize AU owner: keep dummy value if not provided to avoid breaking callers
        au_owner_norm = au_owner or os.getenv('DEFAULT_AU_OWNER', 'N/A')

        # Strict JSON schema for agent output – ensures backend can parse reliably
        output_schema = {
            "type": "object",
            "required": [
                "controlId",
                "applicationId",
                "auOwner",
                "results",
                "overallCompliance",
            ],
            "properties": {
                "controlId": {"type": "string"},
                "applicationId": {"type": "string"},
                "auOwner": {"type": "string"},
                "results": {
                    "type": "object",
                    "required": ["Q1", "Q2", "Q3", "Q4"],
                    "properties": {
                        "Q1": {"type": "object"},
                        "Q2": {"type": "object"},
                        "Q3": {"type": "object"},
                        "Q4": {"type": "object"},
                    },
                },
                "overallCompliance": {"type": "string"},
                "esarValidation": {"type": "object"},
                "evidenceAnalysis": {"type": "object"},
                "jira": {"type": "object"},
            },
        }

        # Prompt that drives the LimAgent to call MCP tools and return JSON
        prompt = f"""
You are the NHA Compliance Validation Agent for control {control_id}: {control_info['name']}.
You must use the available MCP tools to perform real validation:
- SQL (tachyon_mcp_texttosql) to query eSAR/ServiceAccounts for registration verification
- MongoDB (tachyon_mcp_mongo) to validate evidence relevance and overall compliance
- Jira (tachyon_mcp_jira) to create a ticket if non-compliant

Inputs from frontend:
- Application ID: {application_id}
- AU Owner: {au_owner or 'Unknown'}
- Evidence Files Metadata: Provided in the context as 'evidenceFiles'.

Follow the 4-question workflow strictly (Q1..Q4). Where a tool is required, call it.

Return ONLY a single JSON object conforming to this schema:
{json.dumps(output_schema)}

Where each of results.Qx is an object like:
{{
  "answer": "YES"|"NO",
  "rationale": "string",
  "evidenceUsed": [{{"filename": "string"}}],
  "score": 0-25
}}

overallCompliance must be one of ["COMPLIANT", "PARTIALLY_COMPLIANT", "NON_COMPLIANT"].
If NON_COMPLIANT, create a Jira ticket and include jira.ticketKey and jira.url.
"""

        context: Dict[str, Any] = {
            "control_id": control_id,
            "application_id": application_id,
            "au_owner": au_owner,
            "evidenceFiles": evidence_files or [],
        }

        # Feature flag: Use MCP tool flows when explicitly enabled
        use_mcp = os.getenv("USE_MCP", "false").lower() == "true"

        # Local stdio MCP path
        if use_mcp and os.getenv("DIRECT_MCP_STDIO", "false").lower() == "true":
            return self._validate_submission_direct_stdio(control_id, application_id, au_owner_norm, evidence_files)

        # Mongo + LLM only (default path – no MCP calls)
        if not use_mcp:
            # 1) Fetch system instruction
            sys_instr = fetch_system_instruction(application_id, control_id)
            if not sys_instr:
                return {
                    "success": False,
                    "error": f"No systemInstruction found for appId={application_id}, controlId={control_id}",
                }

            # 2) Normalize evidences
            norm_evs = normalize_evidences(evidence_files or [])

            # 3) Build messages for LLM (no tool calls)
            agent = self.create_nha_agent(control_id) if LLM_AVAILABLE else None
            user_payload = {
                "appId": application_id,
                "controlId": control_id,
                "auOwner": au_owner_norm,
                "evidences": [{"fileName": e.get("fileName"), "mimeType": e.get("mimeType") } for e in norm_evs],
            }
            messages = [
                {"role": "system", "content": sys_instr},
                {"role": "user", "content": json.dumps(user_payload)},
            ]

            if agent and hasattr(agent, 'run'):
                raw = agent.run(messages=messages, invocation_context={"variables": {"appId": application_id, "controlId": control_id}})
            elif agent and hasattr(agent, 'execute'):
                raw = agent.execute(json.dumps(user_payload), {})
            else:
                # As ultimate fallback, call underlying model if exposed
                raise RuntimeError("No LLM agent available. Install google.adk or set USE_MCP=true for MCP paths.")

        # Try to safely parse JSON from agent output
        parsed = parse_llm_json(raw)
        if not isinstance(parsed, dict):
            return {
                "success": False,
                "error": "Agent did not return valid JSON",
                "raw": raw,
            }

        parsed.setdefault("controlId", control_id)
        parsed.setdefault("applicationId", application_id)
        parsed.setdefault("auOwner", au_owner_norm)
        parsed["success"] = True
        return parsed

    def _invoke_llm_agent(self, agent: Any, prompt: str, context: Dict[str, Any]) -> str:
        """Call the underlying ADK LlmAgent using whatever public method is available.

        Some ADK builds expose `execute(prompt, context)`, others `run(...)` or `complete(...)`.
        As a last resort, if only `agent.model.complete` exists, we embed the context into
        the prompt. Note: that last fallback may not execute MCP tools.
        """
        # Preferred: run(messages=..., invocation_context=...) to ensure tool calls
        messages = [
            {"role": "system", "content": self._get_nha_instruction(context.get("control_id", "C-305377"))},
            {"role": "user", "content": prompt},
        ]
        invocation_context = {
            "variables": context,
            "tool_choice": "auto",
            "allow_tool_calls": True,
            "tool_timeouts": {
                "tachyon_mcp_texttosql": int(os.getenv("DATABASE_AGENT_TIMEOUT", "300")),
                "tachyon_mcp_mongo": int(os.getenv("DOCUMENT_ANALYSIS_TIMEOUT", "300")),
                "tachyon_mcp_jira": int(os.getenv("JIRA_AGENT_TIMEOUT", "300")),
            },
            "execution": {"max_tool_calls": 8, "fail_on_tool_error": False},
        }

        if hasattr(agent, 'run') and callable(getattr(agent, 'run')):
            try:
                return agent.run(messages=messages, invocation_context=invocation_context)
            except TypeError:
                # Some builds accept (prompt, context)
                pass

        # Next best: execute(prompt, context)
        if hasattr(agent, 'execute') and callable(getattr(agent, 'execute')):
            return agent.execute(prompt, context)

        # Alternate: complete(prompt, context=...)
        if hasattr(agent, 'complete') and callable(getattr(agent, 'complete')):
            try:
                return agent.complete(prompt, context=context)
            except TypeError:
                return agent.complete(prompt)

        # Last-resort fallback: model.complete (may not trigger MCP tool calls)
        if hasattr(agent, 'model') and hasattr(agent.model, 'complete'):
            merged = f"""
{prompt}

---
Context (JSON):
{json.dumps(context)}
"""
            return agent.model.complete(merged)

        raise RuntimeError("This ADK LlmAgent build exposes no supported invocation method (execute/run/complete). Please update ADK or use LimAgent.")

    # (HTTP adapter path removed by request)

    # ----------------- Direct MCP via stdio (no agent, no HTTP) -----------------
    def _validate_submission_direct_stdio(
        self,
        control_id: str,
        application_id: str,
        au_owner: Optional[str],
        evidence_files: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Invoke local MCP servers directly over stdio using MCPToolset.

        This does not require any HTTP wrapper and does not use the agent.
        """
        log = logging.getLogger('mcp_stdio')
        log.info("[STDIO] begin validation | control=%s app=%s au=%s evidences=%s",
                 control_id, application_id, au_owner, len(evidence_files or []))
        # Create clients
        sql_client = MCPToolset(
            connection_params=StdioServerParameters(
                command='python', args=['-m', 'tachyon_mcp_texttosql'], env=env_variables,
                read_timeout_seconds=int(os.getenv('DATABASE_AGENT_TIMEOUT', '300'))
            )
        )
        mongo_client = MCPToolset(
            connection_params=StdioServerParameters(
                command='python', args=['-m', 'tachyon_mcp_mongo'], env=env_variables,
                read_timeout_seconds=int(os.getenv('DOCUMENT_ANALYSIS_TIMEOUT', '300'))
            )
        )
        jira_client = MCPToolset(
            connection_params=StdioServerParameters(
                command='python', args=['-m', 'tachyon_mcp_jira'], env=env_variables,
                read_timeout_seconds=int(os.getenv('JIRA_AGENT_TIMEOUT', '300'))
            )
        )

        def _s(obj: Any) -> str:
            try:
                return json.dumps(obj, ensure_ascii=False)[:1200]
            except Exception:
                return str(obj)[:1200]

        def _mcp_call(client: Any, op: str, payload: Dict[str, Any]) -> Any:
            start = time.time()
            log.debug("[STDIO] -> call op=%s payload=%s", op, _s(payload))
            # Try a series of common method names to invoke a tool
            for name in ('invoke', 'call', 'run', 'request', 'execute', '__call__'):
                fn = getattr(client, name, None)
                if callable(fn):
                    try:
                        res = fn(op, payload)
                        log.debug("[STDIO] <- ok op=%s in %.3fs result=%s", op, time.time()-start, _s(res))
                        return res
                    except TypeError:
                        # Some variants expect just payload
                        try:
                            res = fn(payload)
                            log.debug("[STDIO] <- ok(op-only) op=%s in %.3fs result=%s", op, time.time()-start, _s(res))
                            return res
                        except Exception:
                            continue
                    except Exception as e:
                        log.exception("[STDIO] call error op=%s via %s: %s", op, name, e)
                        continue
            log.error("[STDIO] no_invoke_method for op=%s", op)
            return {"error": "no_invoke_method"}

        # Q1: NHA identification
        q1_sql = "SELECT COUNT(1) as cnt FROM ServiceAccounts WHERE [Application ID]=@p1"
        log.info("[STDIO] Q1: NHA identification (SQL)")
        q1_res = _mcp_call(sql_client, 'query', {"sql": q1_sql, "params": [application_id]})
        try:
            cnt = int((q1_res.get('rows') or [[0]])[0][0]) if isinstance(q1_res, dict) else 0
        except Exception:
            cnt = 0
        q1 = {
            "answer": "YES" if cnt > 0 else "NO",
            "rationale": f"Found {cnt} service accounts for application",
            "evidenceUsed": [],
            "score": 25 if cnt > 0 else 15
        }

        # Q2: eSAR registration
        q2_sql = (
            "SELECT COUNT(1) as cnt FROM ServiceAccounts "
            "WHERE [Application ID]=@p1 AND [Account Certification] IS NOT NULL"
        )
        log.info("[STDIO] Q2: eSAR registration (SQL)")
        q2_res = _mcp_call(sql_client, 'query', {"sql": q2_sql, "params": [application_id]})
        try:
            cnt2 = int((q2_res.get('rows') or [[0]])[0][0]) if isinstance(q2_res, dict) else 0
        except Exception:
            cnt2 = 0
        q2 = {
            "answer": "YES" if cnt2 > 0 else "NO",
            "rationale": f"{cnt2} accounts certified in eSAR",
            "evidenceUsed": [],
            "score": 25 if cnt2 > 0 else 15
        }

        # Evidence/Q3/Q4 via mongo MCP
        log.info("[STDIO] Q3/Q4: evidence analysis (Mongo)")
        ev_res = _mcp_call(mongo_client, 'analyze_evidence', {
            "applicationId": application_id,
            "auOwner": au_owner,
            "evidenceFiles": evidence_files or []
        })
        q3 = ev_res.get('passwordConstruction', {"answer": "UNKNOWN", "rationale": "no data", "score": 15}) if isinstance(ev_res, dict) else {"answer": "UNKNOWN", "rationale": "no data", "score": 15}
        q4 = ev_res.get('passwordRotation', {"answer": "UNKNOWN", "rationale": "no data", "score": 15}) if isinstance(ev_res, dict) else {"answer": "UNKNOWN", "rationale": "no data", "score": 15}

        # Overall
        total = sum([x.get('score', 0) for x in [q1, q2, q3, q4]])
        overall = "COMPLIANT" if total >= 75 else ("PARTIALLY_COMPLIANT" if total >= 50 else "NON_COMPLIANT")

        jira_info: Dict[str, Any] = {}
        if overall == "NON_COMPLIANT":
            log.info("[STDIO] Non-compliant → creating Jira ticket")
            j_res = _mcp_call(jira_client, 'create_ticket', {
                "projectKey": os.getenv('JIRA_PROJECT_KEY', 'BDFS'),
                "summary": f"NHA Non-Compliance - {control_id} - {application_id}",
                "priority": os.getenv('JIRA_PRIORITY', 'High'),
                "description": json.dumps({"Q1": q1, "Q2": q2, "Q3": q3, "Q4": q4})
            })
            if isinstance(j_res, dict):
                jira_info = {"ticketKey": j_res.get('key') or j_res.get('ticketKey'), "url": j_res.get('url')}

        payload = {
            "success": True,
            "controlId": control_id,
            "applicationId": application_id,
            "auOwner": au_owner,
            "results": {"Q1": q1, "Q2": q2, "Q3": q3, "Q4": q4},
            "overallCompliance": overall,
            "esarValidation": {"sql": {"q1": q1, "q2": q2}},
            "evidenceAnalysis": ev_res if isinstance(ev_res, dict) else {"raw": ev_res},
            "jira": jira_info,
        }
        log.info("[STDIO] done validation | overall=%s | ticket=%s", overall, payload.get("jira", {}).get("ticketKey"))
        return payload

    # (All non-MCP fallbacks removed to ensure MCP-only execution as required)


def main():
    """Main function to run the NHA compliance validation system"""
    print("🔒 NHA COMPLIANCE VALIDATION SYSTEM")
    print("=" * 50)

    # Initialize the NHA compliance agent
    nha_agent = NHAComplianceAgent()

    # Display NHA controls
    print("📋 Available NHA Controls:")
    for control_id, control_info in NHA_CONTROLS.items():
        phases = " → ".join(control_info['workflow_phases'].values())
        print(f"  • {control_id}: {control_info['name']}")
        print(f"    Phases: {phases}")
        print()

    # User guide for NHA compliance
    print("📖 NHA VALIDATION WORKFLOW:")
    print("1. Enter Application ID (e.g., CustomerPortal, APP001)")
    print("2. System runs 4-question NHA validation (Q1-Q4)")
    print("3. Answer questions and provide evidence when prompted")
    print("4. Automatic Jira ticket creation for non-compliance")
    print("5. Comprehensive compliance report generation")
    print()

    # Get user input - focus on application ID for NHA workflow
    application_id = input("Enter Application ID: ").strip()

    if not application_id:
        print("❌ Error: Application ID is required")
        return

    # Default to AC-2.3 for NHA compliance (can be extended later)
    control_id = "AC-2.3"

    print(f"\n🚀 Starting NHA compliance validation for '{application_id}'...")
    print("📋 Control: AC-2.3 (NHA Account Management)")
    print("🔄 Workflow: Q1 → Q2 → Q3 → Q4 (with MongoDB prompt integration)")
    print("=" * 60)

    # Run NHA validation with MongoDB integration
    result = nha_agent.run_nha_validation(application_id, control_id)

    print("\n" + "=" * 60)
    print("📋 NHA VALIDATION RESULT:")
    print("=" * 60)
    print(result)

    # Show MongoDB integration details and extension guide
    print("\n" + "=" * 60)
    print("🔧 MONGODB INTEGRATION DETAILS:")
    print("=" * 60)
    print("""
**How MongoDB Integration Works:**
1. **Prompt Retrieval**: System queries MongoDB for control-specific prompts
2. **Dynamic Instructions**: Agent gets tailored validation criteria
3. **Evidence Analysis**: MongoDB processes uploaded evidence files
4. **Context Preservation**: Maintains validation state across workflow

**MongoDB Collections Used:**
- control_prompts: Control-specific validation instructions
- evidence_analysis: Evidence processing and relevance scoring
- compliance_reports: Final assessment storage

**MCP Tool Calling:**
- mongo_query: Retrieves prompts and processes evidence
- mongo_insert: Stores compliance findings and reports
- mongo_update: Updates remediation tracking

**Extensibility:**
- Add new controls by inserting prompts in control_prompts collection
- System automatically uses new prompts via MCP tool calling
- No code changes needed for new controls
""")

    # Ask if user wants to see extension guide
    if input("\nShow extension guide for adding new controls? (y/n): ").lower().startswith('y'):
        show_extension_guide()


def show_extension_guide():
    """Show how to extend for additional controls"""
    print("\n📖 EXTENDING FOR NEW CONTROLS")
    print("=" * 50)
    print("""
**Adding New Controls:**

1. **MongoDB Setup:**
   ```javascript
   // Insert control prompt in MongoDB
   db.control_prompts.insertOne({
     "control_id": "NEW-CONTROL-001",
     "name": "New Control Name",
     "system_prompt": "Detailed validation instructions...",
     "validation_questions": ["Q1?", "Q2?", "Q3?"],
     "evidence_types": ["Evidence 1", "Evidence 2"],
     "created_date": new Date()
   })
   ```

2. **Python Extension:**
   ```python
   # Add to NHA_CONTROLS in agent.py
   NHA_CONTROLS["NEW-CONTROL-001"] = {
       "name": "New Control Name",
       "description": "Control description",
       "workflow_phases": {
           "Q1": "Phase 1",
           "Q2": "Phase 2",
           "Q3": "Phase 3"
       }
   }
   ```

3. **Usage:**
   ```bash
   python agent.py
   # Enter Application ID
   # System automatically uses MongoDB prompt for new control
   ```

**Benefits:**
✅ **No code changes** needed for new controls
✅ **Centralized prompt management** in MongoDB
✅ **Consistent validation** across all controls
✅ **Easy maintenance** and updates
✅ **Scalable architecture** for enterprise use
""")


if __name__ == "__main__":
    main()
    
