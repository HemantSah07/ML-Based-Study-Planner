import time
import logging

logger = logging.getLogger(__name__)

# ── SDK compatibility shim ────────────────────────────────────────────────────
# The project ships with google-generativeai (old SDK).  The new SDK is
# google-genai.  We prefer the new SDK when available; fall back gracefully.
_new_sdk = False
_old_sdk = False

try:
    from google import genai as _genai_new
    from google.genai import types as _types_new
    _new_sdk = True
    logger.info("Gemini provider: using new 'google-genai' SDK.")
except ImportError:
    pass

if not _new_sdk:
    try:
        import google.generativeai as _genai_old
        _old_sdk = True
        logger.warning(
            "Gemini provider: 'google-genai' not found, falling back to "
            "deprecated 'google-generativeai' SDK.  Run: "
            "pip install google-genai"
        )
    except ImportError:
        pass

from app.services.providers.base import BaseAIProvider


class GeminiProvider(BaseAIProvider):
    """
    Gemini AI provider — works with both SDK generations.

    Priority:
      1. google-genai  (new, recommended)
      2. google-generativeai  (old, deprecated but still functional)
    """

    DEFAULT_MODEL_NEW = "gemini-2.5-flash"
    DEFAULT_MODEL_OLD = "gemini-1.5-flash"

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
        self.api_key = api_key

        if _new_sdk:
            self.client = _genai_new.Client(api_key=self.api_key)
            self._mode = "new"
        elif _old_sdk:
            _genai_old.configure(api_key=self.api_key)
            self.client = _genai_old
            self._mode = "old"
        else:
            raise RuntimeError(
                "No Gemini SDK found. Install with: pip install google-genai"
            )

    # ── Core generation ──────────────────────────────────────────────────────

    def generate_content(self, prompt: str, **kwargs) -> str:
        if self._mode == "new":
            return self._generate_new(prompt, **kwargs)
        return self._generate_old(prompt, **kwargs)

    # ── New SDK ──────────────────────────────────────────────────────────────

    def _generate_new(self, prompt: str, **kwargs) -> str:
        max_retries    = kwargs.get("max_retries", 3)
        backoff_factor = kwargs.get("backoff_factor", 2.0)
        initial_delay  = kwargs.get("initial_delay", 1.0)
        model_name     = kwargs.get("model", self.DEFAULT_MODEL_NEW)

        system_instruction = kwargs.get("system_instruction", None)
        response_mime_type = kwargs.get("response_mime_type", None)
        response_schema    = kwargs.get("response_schema", None)

        config = _types_new.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=kwargs.get("temperature", 0.3),
            response_mime_type=response_mime_type,
            response_schema=response_schema,
            max_output_tokens=kwargs.get("max_output_tokens", 8192),
        )

        delay = initial_delay
        for attempt in range(max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config,
                )
                if response.text:
                    return response.text
                raise ValueError("Gemini new-SDK response contained no text.")
            except Exception as e:
                err = str(e)
                retryable = any(
                    t in err for t in [
                        "429", "ResourceExhausted", "Quota", "quota",
                        "500", "503", "ServiceUnavailable", "InternalServerError",
                        "overloaded",
                    ]
                )
                if retryable and attempt < max_retries:
                    is_rate_limit = any(t in err for t in ["429", "ResourceExhausted", "Quota", "quota"])
                    if is_rate_limit:
                        if attempt > 0:
                            # Already retried once for rate limit, fail immediately
                            logger.error(
                                "Gemini (new SDK) rate limit hit again on attempt %d. Failing fast.",
                                attempt + 1
                            )
                            raise
                        sleep_time = 12.0  # short delay for on-demand retry
                        logger.warning(
                            "Gemini (new SDK) rate limit hit on attempt %d. Retrying once in %.1fs...",
                            attempt + 1, sleep_time
                        )
                        time.sleep(sleep_time)
                    else:
                        logger.warning(
                            "Gemini (new SDK) transient error on attempt %d. Retrying in %.1fs...",
                            attempt + 1, delay
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
                else:
                    logger.error(
                        "Gemini (new SDK) permanently failed on attempt %d: %s",
                        attempt + 1, err,
                    )
                    raise
        raise Exception("Gemini: failed to generate content after all retries.")

    # ── Old SDK (fallback) ───────────────────────────────────────────────────

    def _generate_old(self, prompt: str, **kwargs) -> str:
        """
        Fallback using the deprecated google-generativeai SDK.
        Structured JSON schema is not supported; the caller must parse text.
        """
        max_retries    = kwargs.get("max_retries", 3)
        backoff_factor = kwargs.get("backoff_factor", 2.0)
        initial_delay  = kwargs.get("initial_delay", 1.0)
        model_name     = kwargs.get("model", self.DEFAULT_MODEL_OLD)

        system_instruction = kwargs.get("system_instruction", "")
        full_prompt = (
            f"{system_instruction}\n\n{prompt}"
            if system_instruction else prompt
        )

        model = _genai_old.GenerativeModel(model_name)
        delay = initial_delay
        for attempt in range(max_retries + 1):
            try:
                response = model.generate_content(full_prompt)
                return response.text
            except Exception as e:
                err = str(e)
                retryable = any(
                    t in err for t in [
                        "429", "ResourceExhausted", "Quota", "quota",
                        "500", "503", "ServiceUnavailable", "overloaded",
                    ]
                )
                if retryable and attempt < max_retries:
                    is_rate_limit = any(t in err for t in ["429", "ResourceExhausted", "Quota", "quota"])
                    if is_rate_limit:
                        if attempt > 0:
                            logger.error(
                                "Gemini (old SDK) rate limit hit again on attempt %d. Failing fast.",
                                attempt + 1
                            )
                            raise
                        sleep_time = 12.0
                        logger.warning(
                            "Gemini (old SDK) rate limit hit on attempt %d. Retrying once in %.1fs...",
                            attempt + 1, sleep_time
                        )
                        time.sleep(sleep_time)
                    else:
                        logger.warning(
                            "Gemini (old SDK) transient error on attempt %d. Retrying in %.1fs...",
                            attempt + 1, delay
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
                else:
                    logger.error(
                        "Gemini (old SDK) permanently failed on attempt %d: %s",
                        attempt + 1, err,
                    )
                    raise
        raise Exception("Gemini: failed to generate content after all retries.")
