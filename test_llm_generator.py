"""
Test driver for exercising the ADK LLM completion API (streaming + non-stream).

This focuses on avoiding the common `'str' object has no attribute model_copy'`
issue by NOT passing a string for the model. We rely on the model configured in
the `TachyonAdkClient` instance.

Environment variables used (typical gateway setup):
  - MODEL
  - BASE_URL
  - API_KEY
  - CONSUMER_KEY
  - CONSUMER_SECRET
  - USE_CASE_ID
  - UUID
  - CERTS_PATH
  - APIGEE_URL
  - USE_API_GATEWAY
"""

import os
import sys
from typing import Any, Dict, Iterable, Optional

from dotenv import load_dotenv


def _bool_env(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() == "true"


def _safe_preview(txt: str, n: int = 200) -> str:
    s = (txt or "").replace("\n", " ")
    return s[:n] + ("..." if len(s) > n else "")


def _build_messages() -> list:
    """Return messages in a schema compatible with multiple ADK builds."""
    # Preferred: parts-based content
    messages_parts = [
        {
            "role": "system",
            "content": [{"type": "text", "text": "You are a helpful assistant."}],
        },
        {
            "role": "user",
            "content": [{"type": "text", "text": "Say one short sentence confirming connectivity."}],
        },
    ]

    # Simpler fallback: plain text content
    messages_plain = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say one short sentence confirming connectivity."},
    ]

    return [messages_parts, messages_plain]


def create_client():
    """Create and return a configured TachyonAdkClient instance."""
    from tachyon_adk_client import TachyonAdkClient  # Imported here to fail-fast if missing

    model_name = f"openai/{os.getenv('MODEL', 'gemini-2.0-flash')}"
    print(f"[CONFIG] model_name={model_name}")

    client = TachyonAdkClient(
        model_name=model_name,
        base_url=os.getenv("BASE_URL"),
        api_key=os.getenv("API_KEY"),
        consumer_key=os.getenv("CONSUMER_KEY"),
        consumer_secret=os.getenv("CONSUMER_SECRET"),
        use_case_id=os.getenv("USE_CASE_ID"),
        uuid=os.getenv("UUID"),
        certs_path=os.getenv("CERTS_PATH"),
        apigee_url=os.getenv("APIGEE_URL"),
        use_api_gateway=_bool_env("USE_API_GATEWAY", "true"),
        name="LLM_Generator_Tester",
    )
    print("[OK] TachyonAdkClient created")
    return client


def _iter_stream_chunks(stream_obj: Iterable[Any]) -> str:
    """Collect text from a streaming iterator with common chunk shapes."""
    collected: list[str] = []
    for chunk in stream_obj:
        # Handle a variety of possible streaming payload shapes
        # 1) OpenAI-like: {choices: [{delta: {content: "..."}}]}
        try:
            delta = (
                chunk.get("choices", [{}])[0]
                .get("delta", {})
                .get("content")
            )
            if isinstance(delta, str):
                collected.append(delta)
                continue
        except Exception:
            pass

        # 2) Generic: {content: "..."}
        try:
            if isinstance(chunk.get("content"), str):
                collected.append(chunk["content"])
                continue
        except Exception:
            pass

        # 3) Raw string
        if isinstance(chunk, str):
            collected.append(chunk)
            continue

        # 4) Token/event attribute
        token = getattr(chunk, "token", None)
        if isinstance(token, str):
            collected.append(token)

    return "".join(collected)


def try_stream_completion(client: Any, messages: list) -> Optional[str]:
    """Attempt streaming completions using several common ADK interfaces."""
    # A) llm_client.completion(..., stream=True) returns iterator
    try:
        stream = client.llm_client.completion(messages=messages, tools=[], stream=True)  # type: ignore[attr-defined]
        return _iter_stream_chunks(stream)
    except TypeError:
        pass
    except AttributeError:
        pass

    # B) explicit streaming method names
    for meth in ("completion_stream", "stream_completion", "stream"):
        fn = getattr(getattr(client, "llm_client", client), meth, None)
        if callable(fn):
            try:
                stream = fn(messages=messages, tools=[])
                return _iter_stream_chunks(stream)
            except Exception:
                continue

    return None


def try_nonstream_completion(client: Any, messages: list) -> Optional[str]:
    """Non-streaming completion with generic shape handling."""
    try:
        # Important: do not pass a string as model; rely on client's configured model
        result = client.llm_client.completion(messages=messages, tools=[])  # type: ignore[attr-defined]
    except Exception as e:
        print(f"[WARN] non-stream completion failed: {e}")
        return None

    # Try to extract content from common response shapes
    try:
        if hasattr(result, "choices"):
            choices = getattr(result, "choices")
            if isinstance(choices, list) and choices:
                msg = getattr(choices[0], "message", None) or {}
                content = getattr(msg, "content", None) or msg.get("content")
                if isinstance(content, str):
                    return content
    except Exception:
        pass

    try:
        if isinstance(result, dict):
            content = (
                result.get("choices", [{}])[0]
                .get("message", {})
                .get("content")
            )
            if isinstance(content, str):
                return content
    except Exception:
        pass

    return str(result)


def test_llm_generator() -> bool:
    load_dotenv(override=True)
    client = create_client()

    # Try both message shapes for widest compatibility
    for candidate_messages in _build_messages():
        print("\n[TEST] Trying streaming completion...")
        stream_text = try_stream_completion(client, candidate_messages)
        if isinstance(stream_text, str) and stream_text.strip():
            print(f"[STREAM ✓] {_safe_preview(stream_text)}")
            return True

        print("[TEST] Streaming not available or failed; trying non-stream completion...")
        nonstream_text = try_nonstream_completion(client, candidate_messages)
        if isinstance(nonstream_text, str) and nonstream_text.strip():
            print(f"[NON-STREAM ✓] {_safe_preview(nonstream_text)}")
            return True

    print("[✗] No completion path succeeded.")
    return False


def main() -> None:
    ok = test_llm_generator()
    print("\n" + "=" * 70)
    if ok:
        print("✅ SUCCESS: LLM connectivity verified (stream or non-stream path).")
        sys.exit(0)
    else:
        print("❌ FAILURE: Could not obtain a completion. Check credentials and network.")
        sys.exit(2)


if __name__ == "__main__":
    main()


