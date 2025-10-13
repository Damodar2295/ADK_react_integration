import os
from dotenv import load_dotenv

from google.adk.agents.llm_agent import LlmAgent
from tachyon_adk_client import TachyonAdkClient

# Load environment variables
load_dotenv(override=True)

# Validate critical environment variables
required_vars = ['MODEL', 'API_KEY', 'BASE_URL', 'USE_CASE_ID', 'UUID']
missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    print(f"[WARNING] Missing environment variables: {missing_vars}")
    print("Please check your .env file and ensure all required variables are set.")

# Use environment variables directly - no hardcoding
env_variables = dict(os.environ)

# Print configuration for debugging
print("[INFO] Initializing NHA Compliance System")
print(f"[CONFIG] Model: {os.getenv('MODEL', 'Not Set')}")
print(f"[CONFIG] Agent: {os.getenv('ROOT_AGENT_NAME', 'NHA_Compliance_Assistant')}")

# Root Agent - NHA Compliance Validation Orchestrator
root_agent = LlmAgent(
    model=TachyonAdkClient(
        model_name=f"openai/{os.getenv('MODEL', 'gemini-2.0-flash')}",
        base_url=os.getenv('BASE_URL'),
        api_key=os.getenv('API_KEY'),
        use_case_id=os.getenv('USE_CASE_ID'),
        uuid=os.getenv('UUID'),
    ),
    name=os.getenv('ROOT_AGENT_NAME', 'Compliance_Assistant'),
    instruction=f"""
You are the {os.getenv('ROOT_AGENT_NAME', 'Compliance_Assistant')}.
Task: Tiny hello_tachyon verification.

Produce two outputs in order:
1) A single short sentence for humans summarizing Tachyon health and the user's text.
2) On a new line, a JSON object EXACTLY with keys:
   {{
     "ok": <true|false>,
     "tachyon": {{ "baseUrl": "{os.getenv('BASE_URL','')}", "status": "<reachable|unreachable|unknown>" }},
     "echo": "<the user's text>",
     "summary": "<one short sentence summary>"
   }}

Rules:
- Do not add extra keys or commentary to the JSON.
- If Tachyon responds successfully, ok=true and status="reachable"; otherwise ok=false and status="unreachable".
- Keep summary to one sentence.
""",
)
