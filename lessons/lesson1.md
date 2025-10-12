# Lesson 1: Basics of ADK & Reddit Scout Agent

In this lesson, we'll introduce the Google Agent Development Kit (ADK) and build a simple Reddit Scout Agent that fetches recent game development news from Reddit. This agent will serve as a foundation for more advanced multi-agent systems in later lessons.

## Background

The Google ADK provides a framework for building, running, and coordinating AI agents. In this lesson, you'll learn how to:

- Set up your Python environment for ADK
- Create a simple agent that fetches Reddit posts
- Run and interact with your agent using the ADK CLI

## Step 1: Environment Setup

1. **Clone the repository:**

   ```bash
   git clone https://github.com/chongdashu/adk-made-simple
   cd adk-made-simple
   ```

2. **Create and activate a virtual environment (recommended):**

   ```bash
   python -m venv .venv
   # On Windows
   .\.venv\Scripts\activate
   # On macOS/Linux
   source .venv/bin/activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**

   - Copy the example environment file:
     ```bash
     cp .env.example .env
     ```
   - Edit `.env` and add your Google API key and Reddit API credentials:
     ```dotenv
     GOOGLE_API_KEY=YOUR_API_KEY_HERE
     REDDIT_CLIENT_ID=YOUR_REDDIT_CLIENT_ID
     REDDIT_CLIENT_SECRET=YOUR_REDDIT_CLIENT_SECRET
     REDDIT_USER_AGENT=adk-made-simple/0.1 by yourusername
     ```
   - You can obtain a Google API key from [Google AI Studio](https://aistudio.google.com/app/apikey) and Reddit credentials from [Reddit Apps](https://www.reddit.com/prefs/apps).

## Step 2: Understanding the Reddit Scout Agent

The Reddit Scout Agent fetches top post titles from game development subreddits using the Reddit API (via PRAW). The agent is defined in `agents/reddit_scout/agent.py`.

### Agent Code Overview

```python
import random
import os
from google.adk.agents import Agent
from dotenv import load_dotenv
import praw
from praw.exceptions import PRAWException

load_dotenv()

def get_reddit_gamedev_news(subreddit: str, limit: int = 5) -> dict[str, list[str]]:
    """
    Fetches top post titles from a specified subreddit using the Reddit API.
    """
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT")
    if not all([client_id, client_secret, user_agent]):
        return {subreddit: ["Error: Reddit API credentials not configured."]}
    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )
        reddit.subreddits.search_by_name(subreddit, exact=True)
        sub = reddit.subreddit(subreddit)
        top_posts = list(sub.hot(limit=limit))
        titles = [post.title for post in top_posts]
        if not titles:
            return {subreddit: [f"No recent hot posts found in r/{subreddit}."]}
        return {subreddit: titles}
    except PRAWException as e:
        return {subreddit: [f"Error accessing r/{subreddit}: {e}"]}
    except Exception as e:
        return {subreddit: [f"An unexpected error occurred: {e}"]}

# Define the Agent
agent = Agent(
    name="reddit_scout_agent",
    description="A Reddit scout agent that searches for the most relevant posts in a given subreddit",
    model="gemini-1.5-flash-latest",
    instruction=(
        "You are the Game Dev News Scout. Your primary task is to fetch and summarize game development news. "
        "1. **Identify Intent:** Determine if the user is asking for game development news or related topics. "
        "2. **Determine Subreddit:** Identify which subreddit(s) to check. Use 'gamedev' by default if none are specified. "
        "3. **Synthesize Output:** Take the exact list of titles returned by the tool. "
        "4. **Format Response:** Present the information as a concise, bulleted list. Clearly state which subreddit(s) the information came from. "
        "5. **MUST CALL TOOL:** You **MUST** call the `get_reddit_gamedev_news` tool with the identified subreddit(s). Do NOT generate summaries without calling the tool first."
    ),
    tools=[get_reddit_gamedev_news],
)
```

## Step 3: Running the Reddit Scout Agent

1. **Navigate to the agent directory:**

   ```bash
   cd agents/reddit_scout
   ```

2. **Run the agent using the ADK CLI:**

   ```bash
   adk run reddit_scout
   ```
   _or from the project root:_
   ```bash
   adk run agents/reddit_scout
   ```

3. **Interact with the agent:**

   - The agent will start, and you can type prompts such as:
     - "What are the latest posts in r/gamedev?"
     - "Show me hot topics from r/unrealengine."
   - The agent will fetch and display the top post titles as a bulleted list.

## Step 4: Troubleshooting

- **Missing API Keys:** Ensure your `.env` file is correctly configured and loaded.
- **Reddit API Errors:** Double-check your Reddit credentials and that the subreddits exist.
- **ADK CLI Not Found:** Make sure `google-adk` is installed in your environment.

## Conclusion

In this lesson, you learned how to set up the ADK, configure environment variables, and build a simple Reddit Scout Agent. This agent forms the basis for more advanced multi-agent systems in future lessons.

---

_Next: Lesson 2 will introduce multi-agent coordination, asynchronous tool use, and text-to-speech capabilities!_ 