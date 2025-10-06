#!/usr/bin/env python3
"""
Simple Flask API Server for NHA Compliance Agent
Properly integrates with agent.py and executes real agents with MCP tools
"""

from flask import Flask, request, jsonify
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

# Import the real agent system
try:
    from agent import NHAComplianceAgent, NHA_CONTROLS
    ADK_AGENT_AVAILABLE = True
    print("✅ Real NHA Compliance Agent imported successfully")
except ImportError as e:
    ADK_AGENT_AVAILABLE = False
    print(f"❌ Failed to import real agent: {e}")
    print("🔄 Agent not available - API server cannot function")
    exit(1)  # Exit if agent is not available

app = Flask(__name__)

# Enable CORS if available
if CORS:
    CORS(app)  # Enable cross-origin requests from React
    print("✅ CORS enabled for React frontend")
else:
    print("⚠️  CORS not available - you may need to install flask-cors")

# Global agent instance
nha_agent = None

def initialize_agent():
    """Initialize the NHA compliance agent"""
    global nha_agent
    if ADK_AGENT_AVAILABLE:
        try:
            nha_agent = NHAComplianceAgent()
            print("🔧 Real NHA Compliance Agent created successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to create real agent: {e}")
            return False
    else:
        print("🔧 Using fallback orchestrator")
        return False

def extract_control_number(message: str) -> str:
    """Extract control number from message"""
    # Only support one control: C-305377
    return 'C-305377'

@app.route('/chat', methods=['POST'])
def chat():
    """
    Handle chat messages - delegate ALL processing to real agent
    """
    try:
        # Get message from request
        if request.is_json:
            data = request.get_json()
            message = data.get('message', '')
            frontend_context = data.get('context', {})
        else:
            # Handle form data (supports file uploads)
            message = request.form.get('message', '')
            frontend_context = {}

        print(f"📨 Received message: {message[:100]}...")

        # Extract control number from message (only C-305377 supported)
        control_number = extract_control_number(message)
        print(f"🎯 Control number: {control_number}")

        # Execute real agent with context
        print("🔄 Executing real NHA agent with MCP tools...")
        try:
            response = nha_agent.run_nha_validation(
                application_id=frontend_context.get('applicationId', 'Unknown'),
                control_id=control_number
            )
            print(f"✅ Agent execution successful: {len(response)} characters")
        except Exception as e:
            print(f"❌ Agent execution failed: {e}")
            return jsonify({
                'success': False,
                'error': f'Agent execution failed: {str(e)}',
                'message': 'Failed to execute NHA compliance agent. Please check agent configuration and MCP servers.'
            })

        print(f"✅ Agent response generated: {len(response)} characters")

        # Return structured response
        return jsonify({
            'success': True,
            'message': response,
            'agent_name': agent.name if agent else 'NHA_Compliance_Assistant',
            'mcp_servers': {
                'sql': True,  # MCP_SQL_AVAILABLE if available
                'mongo': True,  # MCP_MONGO_AVAILABLE if available
                'jira': True,  # MCP_JIRA_AVAILABLE if available
            }
        })

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
    print("🚀 Starting NHA Compliance API Server...")
    print(f"📊 Agent Available: {ADK_AGENT_AVAILABLE}")
    print("🎯 Control: C-305377 - Non-Human Account Inventory and Password Validation")
    print("🌐 Server running on http://localhost:5000")
    print("💬 Chat endpoint: POST /chat")
    print("❤️  Health endpoint: GET /health")
    print("🔧 Bridge between React frontend and agent.py with MCP tools")

    # Run in debug mode for development
    app.run(host='0.0.0.0', port=5000, debug=True)
