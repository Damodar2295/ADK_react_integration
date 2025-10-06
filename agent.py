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

# Load environment variables
load_dotenv(override=True)

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

        # Always use the LimAgent+MCP toolsets for execution to satisfy compliance workflow
        if not LLM_AVAILABLE:
            return {
                "success": False,
                "error": "LlmAgent is not available in this environment. Please install google.adk and enable MCP toolsets.",
            }

        # Create the agent with all MCP toolsets
        agent = self.create_nha_agent(control_id)

        # Execute the LimAgent
        raw = agent.execute(prompt, context)

        # Try to safely parse JSON from agent output
        parsed = _safe_parse_json(raw)
        if not isinstance(parsed, dict):
            return {
                "success": False,
                "error": "Agent did not return valid JSON",
                "raw": raw,
            }

        parsed.setdefault("controlId", control_id)
        parsed.setdefault("applicationId", application_id)
        parsed.setdefault("auOwner", au_owner)
        parsed["success"] = True
        return parsed

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
