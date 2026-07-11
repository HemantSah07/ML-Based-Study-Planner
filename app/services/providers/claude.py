import time
import logging
import anthropic
from app.services.providers.base import BaseAIProvider

logger = logging.getLogger(__name__)


class ClaudeProvider(BaseAIProvider):
    """Anthropic Claude provider for SmartStudy AI service."""

    DEFAULT_MODEL = "claude-3-5-haiku-20241022"   # fast & affordable
    MAX_TOKENS = 4096

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set.")
        self.client = anthropic.Anthropic(api_key=api_key)

    def generate_content(self, prompt: str, **kwargs) -> str:
        """Single-turn generation (used for lesson material, caching, etc.)."""
        max_retries = kwargs.get("max_retries", 3)
        backoff_factor = kwargs.get("backoff_factor", 2.0)
        delay = kwargs.get("initial_delay", 1.0)
        model = kwargs.get("model", self.DEFAULT_MODEL)
        max_tokens = kwargs.get("max_tokens", self.MAX_TOKENS)
        system_msg = kwargs.get("system", "You are a helpful AI study tutor.")

        for attempt in range(max_retries + 1):
            try:
                message = self.client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system_msg,
                    messages=[{"role": "user", "content": prompt}]
                )
                return message.content[0].text
            except Exception as e:
                err_msg = str(e)
                is_retryable = any(
                    t in err_msg for t in ["529", "529", "overloaded", "rate_limit", "timeout", "500", "503"]
                )
                if is_retryable and attempt < max_retries:
                    logger.warning(
                        f"Claude API attempt {attempt + 1} failed: {err_msg}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                    delay *= backoff_factor
                else:
                    logger.error(f"Claude API permanently failed on attempt {attempt + 1}: {err_msg}")
                    raise
        raise Exception("Claude: failed to generate content after all retries.")

    def chat(self, messages: list, system: str, **kwargs) -> str:
        """
        Multi-turn conversation support.

        :param messages: List of dicts with 'role' ('user'/'assistant') and 'content'.
        :param system:   System-level instruction string.
        :returns:        The assistant's reply text.
        """
        max_retries = kwargs.get("max_retries", 2)
        model = kwargs.get("model", self.DEFAULT_MODEL)
        max_tokens = kwargs.get("max_tokens", self.MAX_TOKENS)
        delay = 1.0

        for attempt in range(max_retries + 1):
            try:
                response = self.client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=messages
                )
                return response.content[0].text
            except Exception as e:
                err_msg = str(e)
                is_retryable = any(
                    t in err_msg for t in ["overloaded", "rate_limit", "timeout", "500", "503"]
                )
                if is_retryable and attempt < max_retries:
                    logger.warning(f"Claude chat attempt {attempt + 1} failed: {err_msg}. Retrying...")
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.error(f"Claude chat failed permanently: {err_msg}")
                    raise
        raise Exception("Claude: chat failed after all retries.")
