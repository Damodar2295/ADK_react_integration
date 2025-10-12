import os
import sys
import logging
import argparse
import uvicorn
import asyncio
from contextlib import AsyncExitStack
from dotenv import load_dotenv

from pydantic import BaseModel

from .agent import root_agent  # coroutine or agent
from common.a2a_server import AgentRequest, AgentResponse, create_agent_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Load env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

class SimpleTaskManager:
    def __init__(self, agent):
        self.agent = agent

    async def process_task(self, message: str, context: dict, session_id: str | None):
        # Build minimal ADK-style content from message/context
        from google.genai import types as adk_types

        # Convert context to a short JSON string for the model
        import json
        try:
            ctx_str = json.dumps(context or {})
        except Exception:
            ctx_str = str(context)

        request_content = adk_types.Content(role="user", parts=[
            adk_types.Part(text=message or "Evaluate IAM evidences"),
            adk_types.Part(text=ctx_str),
        ])

        # Call the agent model; collect final message text only (no function call here)
        events_text = ""
        try:
            runner = None
            from google.adk.runners import Runner
            from google.adk.sessions import InMemorySessionService
            from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService

            session_service = InMemorySessionService()
            artifact_service = InMemoryArtifactService()
            runner = Runner(agent=self.agent, app_name="iam_evidence", session_service=session_service, artifact_service=artifact_service)

            events_async = runner.run_async(user_id=context.get("user_id", "a2a_user"), session_id=session_id or "a2a_session", new_message=request_content)
            async for event in events_async:
                if event.is_final_response() and event.content and event.content.role == "model":
                    if event.content.parts and event.content.parts[0].text:
                        events_text = event.content.parts[0].text
                        break
        except Exception as e:
            logger.error("Error running agent: %s", e, exc_info=True)
            return {"message": f"Error: {e}", "status": "error", "data": {"error_type": type(e).__name__}}

        # Try to parse model text as JSON result
        try:
            import json
            parsed = json.loads(events_text)
        except Exception:
            parsed = {"Answer": events_text, "Quality": "N/A", "Source": "", "Summary": "", "Reference": ""}

        return {
            "message": "ok",
            "status": "success",
            "data": {"result": parsed}
        }

async def main():
    logger.info("Starting IAM Evidence A2A server...")

    # root_agent may be coroutine or agent
    agent_instance = root_agent
    if asyncio.iscoroutine(agent_instance):
        agent_instance, exit_stack = await root_agent
    else:
        exit_stack = AsyncExitStack()
        await exit_stack.__aenter__()

    async with exit_stack:
        task_manager = SimpleTaskManager(agent_instance)
        host = os.getenv("IAM_EVIDENCE_A2A_HOST", "127.0.0.1")
        port = int(os.getenv("IAM_EVIDENCE_A2A_PORT", 8003))

        app = create_agent_server(name=agent_instance.name, description=agent_instance.description, task_manager=task_manager)
        logger.info("IAM Evidence A2A server starting on %s:%s", host, port)
        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user.")
        sys.exit(0)
    except Exception as e:
        logger.error("Startup error: %s", e, exc_info=True)
        sys.exit(1)
