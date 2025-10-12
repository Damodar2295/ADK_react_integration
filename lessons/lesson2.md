# Lesson 2: Multi-Agent Systems, Summarization, and Text-to-Speech

In this lesson, we expand on the Reddit Scout Agent by introducing multiple agents and coordination between them. You'll learn how to build a multi-agent system that can fetch Reddit news, summarize it, and convert text to speech using ElevenLabs—all orchestrated via the Google ADK.

## Background

By the end of Lesson 1, you had a working Reddit Scout Agent. In this lesson, you'll:

- Learn about asynchronous tool use and MCP integration
- Build a Summarizer Agent for newscaster-style summaries
- Build a Speaker Agent that uses ElevenLabs TTS via MCP
- Combine these into a Coordinator Agent that delegates tasks

## Step 1: Project Structure for Multi-Agent Systems

Your `agents/` directory now includes:

```
agents/
├── reddit_scout/         # Lesson 1: Synchronous Reddit Scout Agent
│   └── agent.py
├── async_reddit_scout/   # Lesson 2: Async Reddit Scout Agent (MCP)
│   └── agent.py
├── summarizer/           # Lesson 2: Newscaster Summarizer Agent
│   └── agent.py
├── speaker/              # Lesson 2: Speaker Agent (TTS via ElevenLabs MCP)
│   └── agent.py
└── coordinator/          # Lesson 2: Coordinator Agent
    └── agent.py
```

## Step 2: The Asynchronous Reddit Scout Agent

The async Reddit Scout Agent connects to an external MCP server (e.g., `mcp-reddit`) to fetch hot threads from Reddit. This allows for more flexible, scalable tool integration.

### Example: `agents/async_reddit_scout/agent.py`

```python
import asyncio
import os
from google.adk.agents import Agent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

async def get_tools_async():
    tools, exit_stack = await MCPToolset.from_server(
        connection_params=StdioServerParameters(
            command='uvx',
            args=['--from', 'git+https://github.com/adhikasp/mcp-reddit.git', 'mcp-reddit'],
        )
    )
    return tools, exit_stack

async def create_agent():
    tools, exit_stack = await get_tools_async()
    agent_instance = Agent(
        name="async_reddit_scout_agent",
        description="A Reddit scout agent that searches for hot posts in a given subreddit using an external MCP Reddit tool.",
        model="gemini-1.5-flash-latest",
        instruction=(
            "You are the Async Reddit News Scout. Your task is to fetch hot post titles from any subreddit using the connected Reddit MCP tool. "
            "1. **Identify Subreddit:** Determine which subreddit the user wants news from. Default to 'gamedev' if none is specified. "
            "2. **Call Discovered Tool:** You **MUST** look for and call the tool named 'fetch_reddit_hot_threads' with the identified subreddit name and optionally a limit. "
            "3. **Present Results:** The tool will return a formatted string containing the hot post information or an error message. "
            "4. **Handle Missing Tool:** If you cannot find the required Reddit tool, inform the user. "
            "5. **Do Not Hallucinate:** Only provide information returned by the tool."
        ),
        tools=tools,
    )
    return agent_instance, exit_stack

root_agent = create_agent()
```

## Step 3: The Summarizer Agent

The Summarizer Agent takes a list of Reddit post titles and produces a concise, newscaster-style summary.

### Example: `agents/summarizer/agent.py`

```python
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

def create_summarizer_agent():
    llm = LiteLlm(model="gemini/gemini-1.5-pro-latest", api_key=os.environ.get("GOOGLE_API_KEY"))
    summarizer = Agent(
        name="newscaster_summarizer_agent",
        description="Summarizes a list of Reddit post titles in a newscaster style.",
        model=llm,
        instruction=(
            "You are a news anchor summarizing Reddit headlines. "
            "Given a list of post titles, provide a concise, engaging summary in a professional newscaster style. "
            "Highlight key themes or interesting points found only in the titles. "
            "Start with an anchor intro like 'Here are today's top stories from the subreddit...' or similar. Keep it brief. "
            "Refer to subreddits by name, no need to mention 'r/'."
        )
    )
    return summarizer

root_agent = create_summarizer_agent()
```

## Step 4: The Speaker Agent (Text-to-Speech)

The Speaker Agent uses ElevenLabs TTS via MCP to convert text into speech audio files. It is designed to be called by other agents (like the Coordinator) or directly by users.

### Example: `agents/speaker/agent.py`

```python
import asyncio
import os
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters
from google.adk.models.lite_llm import LiteLlm

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

async def create_agent():
    tools, exit_stack = await MCPToolset.from_server(
        connection_params=StdioServerParameters(
            command='uvx',
            args=['elevenlabs-mcp'],
            env={'ELEVENLABS_API_KEY': os.environ.get('ELEVENLABS_API_KEY', '')}
        )
    )
    llm = LiteLlm(model="gemini/gemini-1.5-flash-latest", api_key=os.environ.get("GOOGLE_API_KEY"))
    agent_instance = Agent(
        name="tts_speaker_agent",
        description="Converts provided text into speech using ElevenLabs TTS MCP.",
        instruction=(
            "You are a Text-to-Speech agent. Convert user text to speech audio files.\n\n"
            "IMPORTANT FORMATTING RULES:\n"
            "1. Always call the text_to_speech tool with voice_name='Will'\n"
            "2. When the tool returns a file path, format your response like this example:\n"
            "   'I've converted your text to speech. The audio file is saved at `/path/to/file.mp3`'\n"
            "3. Make sure to put ONLY the file path inside backticks (`), not any additional text\n"
            "4. Never modify or abbreviate the path\n\n"
            "This exact format is critical for proper processing."
        ),
        model=llm,
        tools=tools,
    )
    return agent_instance, exit_stack

root_agent = create_agent()
```

## Step 5: The Coordinator Agent

The Coordinator Agent orchestrates the other agents. It can:
- Fetch Reddit news (via async Reddit Scout)
- Summarize it (via Summarizer)
- Convert summaries or lists to speech (via Speaker)

### Example: `agents/coordinator/agent.py`

```python
import os
from contextlib import AsyncExitStack
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from dotenv import load_dotenv

from async_reddit_scout.agent import create_agent as create_reddit_scout_agent
from summarizer.agent import create_summarizer_agent
from speaker.agent import create_agent as create_speaker_agent

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

async def create_coordinator_agent():
    exit_stack = AsyncExitStack()
    await exit_stack.__aenter__()
    reddit_agent, reddit_stack = await create_reddit_scout_agent()
    await exit_stack.enter_async_context(reddit_stack)
    summarizer_agent = create_summarizer_agent()
    speaker_agent, speaker_stack = await create_speaker_agent()
    await exit_stack.enter_async_context(speaker_stack)
    coordinator_llm = LiteLlm(model="gemini/gemini-1.5-pro-latest", api_key=os.environ.get("GOOGLE_API_KEY"))
    coordinator = Agent(
        name="coordinator_agent",
        description="Coordinates finding Reddit posts, summarizing titles, and converting text to speech.",
        model=coordinator_llm,
        instruction=(
            "You manage three sub-agents: Reddit Scout, Summarizer, and Speaker."
            "\n1. When the user asks for 'hot posts', delegate to Reddit Scout and return its raw list."
            "\n2. If the user then asks for a 'summary', delegate the Reddit Scout's exact output to Summarizer and return its summary."
            "\n3. If the user asks you to 'speak' or 'read', determine if they want the summary (if available) or the original list, then delegate the appropriate text to Speaker and return its result (URL)."
            "\n4. For other queries, respond directly without delegation."
        ),
        sub_agents=[reddit_agent, summarizer_agent, speaker_agent]
    )
    return coordinator, exit_stack

root_agent = create_coordinator_agent()
```

## Step 6: Running and Testing the Agents

1. **Install dependencies and set up your `.env` as in Lesson 1.**
2. **Start the ADK web server for async agents:**

   ```bash
   cd agents
   adk web
   ```

3. **Interact with the Coordinator Agent via the web UI:**
   - Ask for Reddit news, summaries, or to "read aloud" the results.
   - The Coordinator will delegate to the appropriate sub-agent(s).

## Troubleshooting

- **MCP/uvx not found:** Ensure `uvx` is installed (`pip install uvx`) and available in your PATH.
- **Missing API keys:** Check your `.env` for all required keys (Google, Reddit, ElevenLabs).
- **Async errors:** Make sure you are running the ADK in web mode for async agents.

## Conclusion

In this lesson, you learned how to build and coordinate multiple agents using the ADK, including asynchronous tool use and text-to-speech. The Coordinator Agent demonstrates how to combine specialized agents into a powerful multi-step workflow.

---

_Next: Lesson 3 will show how to build custom UIs for your agents!_ 