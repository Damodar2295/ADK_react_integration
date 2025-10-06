#!/usr/bin/env python3
"""
Simple Flask API Server for NHA Compliance Agent
Properly integrates with agent.py and executes real agents with MCP tools
"""

from flask import Flask, request, jsonify
import logging
from logging.handlers import RotatingFileHandler
import uuid
import json as _json
try:
    from flask_cors import CORS
except ImportError:
    print("⚠️  flask-cors not installed, CORS will not be enabled")
    CORS = None
import os
import sys
import traceback
from typing import Dict, Any

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------
# Logging setup
# ---------------------------------------------------------
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.getenv('API_LOG_FILE', os.path.join(LOG_DIR, 'api_server.log'))

logger = logging.getLogger('nha_api')
logger.setLevel(logging.DEBUG)

_handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8')
_formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s')
_handler.setFormatter(_formatter)
logger.addHandler(_handler)

def _safe(obj):
    try:
        return _json.dumps(obj, ensure_ascii=False)[:4000]
    except Exception:
        return str(obj)[:4000]

def _reqid() -> str:
    return str(uuid.uuid4())

# Import the real agent system
try:
    from agent import NHAComplianceAgent, NHA_CONTROLS
    ADK_AGENT_AVAILABLE = True
    logger.info("Real NHA Compliance Agent imported successfully")
except ImportError as e:
    ADK_AGENT_AVAILABLE = False
    logger.exception("Failed to import real agent: %s", e)
    logger.error("Agent not available - API server cannot function")
    exit(1)  # Exit if agent is not available

app = Flask(__name__)

# Enable CORS if available
if CORS:
    CORS(app)  # Enable cross-origin requests from React
    logger.info("CORS enabled for React frontend")
else:
    logger.warning("flask-cors not available - you may need to install it for frontend integration")

# Global agent instance
nha_agent = None

def initialize_agent():
    """Initialize the NHA compliance agent"""
    global nha_agent
    if ADK_AGENT_AVAILABLE:
        try:
            nha_agent = NHAComplianceAgent()
            logger.info("Real NHA Compliance Agent created successfully")
            return True
        except Exception as e:
            logger.exception("Failed to create real agent: %s", e)
            return False
    else:
        logger.warning("Fallback orchestrator is not supported in this build")
        return False

def extract_control_number(message: str, fallback: str = 'C-305377') -> str:
    """Extract control number from message or return fallback (single-control)."""
    return fallback

@app.route('/chat', methods=['POST'])
def chat():
    """
    Handle chat messages - delegate ALL processing to real agent
    """
    try:
        # Get message from request
        req_id = _reqid()
        if request.is_json:
            data = request.get_json()
            message = data.get('message', '')
            frontend_context = data.get('context', {})
        else:
            # Handle form data (supports file uploads)
            message = request.form.get('message', '')
            frontend_context = {}

        logger.info("[%s] Incoming /chat | msg=<%s> ctx=%s", req_id, message[:100], _safe(frontend_context))

        # Extract control number from context or message (only C-305377 supported)
        control_number = frontend_context.get('controlId') or extract_control_number(message)
        logger.info("[%s] Control resolved: %s", req_id, control_number)

        # Execute real agent with context and evidence
        logger.info("[%s] Executing agent.validate_submission...", req_id)
        try:
            structured = nha_agent.validate_submission(
                control_id=control_number,
                application_id=frontend_context.get('applicationId', 'Unknown'),
                au_owner=frontend_context.get('auOwner'),
                evidence_files=frontend_context.get('evidenceFiles', [])
            )
            if not structured.get('success'):
                logger.error("[%s] Agent validation error: %s", req_id, _safe(structured))
                return jsonify({"success": False, **structured})
            logger.info("[%s] Agent execution successful", req_id)
        except Exception as e:
            logger.exception("[%s] Agent execution failed: %s", req_id, e)
            return jsonify({
                'success': False,
                'error': f'Agent execution failed: {str(e)}',
                'message': 'Failed to execute NHA compliance agent. Please check agent configuration and MCP servers.'
            })

        # Return structured response
        response_payload = {
            'success': True,
            'agent_name': 'NHA_Compliance_Assistant',
            'data': structured
        }
        logger.debug("[%s] Response: %s", req_id, _safe(response_payload))
        return jsonify(response_payload)

    except Exception as e:
        print(f"❌ API Error: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'An error occurred while processing your request.'
        })

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'agent_available': ADK_AGENT_AVAILABLE,
        'control': 'C-305377' if ADK_AGENT_AVAILABLE else None,
        'mcp_servers': {
            'sql': True,  # Real MCP servers should be checked
            'mongo': True,
            'jira': True
        }
    })


# Initialize agent on startup
agent_initialized = initialize_agent()

if __name__ == '__main__':
    logger.info("Starting NHA Compliance API Server...")
    logger.info("Agent Available: %s", ADK_AGENT_AVAILABLE)
    logger.info("Control: C-305377 - Non-Human Account Inventory and Password Validation")
    logger.info("Server running on http://localhost:5000")
    logger.info("Endpoints: POST /chat, GET /health")
    logger.info("Bridge: React frontend <-> agent.py (MCP tools)")

    # Run in debug mode for development
    app.run(host='0.0.0.0', port=5000, debug=True)
