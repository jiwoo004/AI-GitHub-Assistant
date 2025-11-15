import os
import time
from typing import Optional, Dict, Any

try:
    import ollama
except Exception:
    ollama = None

# Default values
DEFAULT_MODEL_NAME = "exaone3.5:2.4b"
DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_AI_TIMEOUT = 60.0

# These can be updated at runtime
MODEL_NAME = DEFAULT_MODEL_NAME
OLLAMA_HOST = DEFAULT_OLLAMA_HOST

# If set to '1' then network calls to ollama will be skipped and mock responses used
MOCK_MODE = os.environ.get("AI_MOCK_MODE", "0") == "1"
DEBUG_MODE = os.environ.get("AI_DEBUG", "0") == "1"
AI_TIMEOUT = DEFAULT_AI_TIMEOUT


def configure_client(config: Dict[str, Any]):
    """Configure the Ollama client from the application config."""
    global MODEL_NAME, OLLAMA_HOST, AI_TIMEOUT
    MODEL_NAME = config.get("ollama_model", DEFAULT_MODEL_NAME)
    AI_TIMEOUT = config.get("ai_timeout_seconds", DEFAULT_AI_TIMEOUT)


def _ollama_available() -> bool:
    return ollama is not None and not MOCK_MODE


def ask(question: str, timeout: Optional[float] = None, retries: int = 1) -> str:
    """Send a chat-style question to the Ollama model and return text response.

    - timeout: seconds to wait for a response (not currently enforced by ollama SDK,
      but used to limit retry loops).
    - retries: number of attempts on failure.

    If MOCK_MODE is enabled or the ollama package is not available, returns a
    simple placeholder response so the GUI can be tested without a model.
    """
    if MOCK_MODE or not _ollama_available():
        # Return a deterministic mock response for UI testing
        return "feat: update (mocked)"

    if DEBUG_MODE:
        print(f"--- AI PROMPT ---\n{question}\n-----------------")

    last_exc = None
    for attempt in range(max(1, retries)):
        try:
            client = ollama.Client(host=OLLAMA_HOST, timeout=timeout)
            response = client.chat(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": question}],
            )
            content = response.get("message", {}).get("content", "")

            # Handle markdown code blocks for JSON
            if content.startswith("```json"):
                content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]
            elif content.startswith("```"):
                content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
            
            if DEBUG_MODE:
                print(f"--- AI RAW RESPONSE ---\n{content}\n-----------------------")

            return content.strip()
        except Exception as e:
            last_exc = e
            # Small backoff before retrying
            time.sleep(0.5 + attempt * 0.5)

    # If we reach here, all retries failed
    raise RuntimeError(f"Ollama request failed: {last_exc}")
