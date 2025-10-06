# Flask API Server for NHA Compliance Agent

This is a simple Flask API server that properly integrates with the `agent.py` file and executes real agents with MCP tools.

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements-api.txt
```

### 2. Start MCP Servers (in separate terminals)

```bash
# Terminal 1: SQL Server MCP
python -m tachyon_mcp_texttosql

# Terminal 2: MongoDB MCP
python -m tachyon_mcp_mongo

# Terminal 3: Jira MCP
python -m tachyon_mcp_jira
```

### 3. Start API Server

```bash
# Terminal 4: API Server
python api_server.py
```

### 4. Start React Frontend

```bash
# Terminal 5: React App
npm run dev
```

## 📡 API Endpoints

### POST `/chat`
**Purpose:** Process chat messages through real agent

**Request:**
```json
{
  "message": "Does this application have non-human accounts?",
  "context": {
    "applicationId": "CustomerPortal",
    "controlId": "C-305377"
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "🔍 NHA Compliance Validation Response...",
  "agent_name": "NHA_Compliance_Assistant",
  "mcp_servers": {
    "sql": true,
    "mongo": true,
    "jira": true
  }
}
```

### GET `/health`
**Purpose:** Health check endpoint

**Response:**
```json
{
  "status": "healthy",
  "agent_available": true,
  "control": "C-305377",
  "mcp_servers": {
    "sql": true,
    "mongo": true,
    "jira": true
  }
}
```

## 🔧 How It Works

### 1. Message Processing
```python
@app.route('/chat', methods=['POST'])
def chat():
    # Extract message and context from request
    data = request.get_json()
    message = data.get('message', '')
    context = data.get('context', {})

    # Extract control number from message
    control_number = extract_control_number(message)

    # Execute real agent
    response = nha_agent.run_nha_validation(
        application_id=context.get('applicationId', 'Unknown'),
        control_id=control_number
    )

    return jsonify({
        'success': True,
        'message': response,
        'agent_name': 'NHA_Compliance_Assistant'
    })
```

### 2. Agent Integration
- ✅ **Real Agent Execution**: Uses `NHAComplianceAgent` from `agent.py`
- ✅ **MCP Tool Integration**: Connects to real SQL Server, MongoDB, and Jira
- ✅ **4-Question Workflow**: Supports the complete NHA validation process
- ✅ **Error Handling**: Proper fallback when agent is unavailable

### 3. CORS Support
- ✅ **Cross-Origin Requests**: Allows React frontend to communicate
- ✅ **Preflight Handling**: Supports complex requests from browsers

## 🎯 Architecture

```
React Frontend (Port 3000)
       ↓ HTTP POST /chat
Flask API Server (Port 5000)
       ↓ Agent Execution
Python Agent (agent.py)
       ↓ MCP Tools
SQL Server + MongoDB + Jira
```

## 🔍 Integration Details

### Real Agent Execution
The API server properly executes the real agent by:
1. **Importing** `NHAComplianceAgent` from `agent.py`
2. **Creating** agent instance with MCP tools configured
3. **Calling** `run_nha_validation()` with proper parameters
4. **Returning** structured responses to frontend

### MCP Server Integration
The agent connects to real MCP servers:
- **SQL Server**: Database queries for NHA data
- **MongoDB**: Evidence analysis and prompt storage
- **Jira**: Ticket creation for non-compliance

## 🚨 Troubleshooting

### Agent Not Available
If you see "NHA Compliance Agent not available":
1. Check that `agent.py` exists in the same directory
2. Ensure all environment variables are set
3. Verify MCP servers are running
4. Check Python path and imports

### MCP Servers Not Found
If MCP tools are not available:
1. Install tachyon MCP packages: `pip install tachyon-mcp-*`
2. Start MCP servers in separate terminals
3. Check network connectivity and ports

### CORS Issues
If React frontend can't connect:
1. Install flask-cors: `pip install flask-cors`
2. Check that CORS is enabled in the API server
3. Verify frontend is making requests to correct port (5000)

## 📊 Expected Workflow

1. **Frontend** sends message to `/chat`
2. **API Server** extracts control number from message
3. **Agent** executes 4-question NHA validation workflow
4. **MCP Tools** query real databases and systems
5. **Response** returned to frontend with results

## 🔧 Configuration

The API server is configured for:
- **Single Control:** C-305377 - Non-Human Account Inventory and Password Validation
- **MCP Integration:** Real SQL Server, MongoDB, and Jira servers
- **Context Passing:** Maintains frontend state and passes to agent.py

No additional configuration needed - just ensure `agent.py` is properly configured with your database credentials and MCP server endpoints.
