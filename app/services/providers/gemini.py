import time
import logging
from google import genai
from google.genai import types
from google.genai.errors import APIError
from app.services.providers.base import BaseAIProvider

logger = logging.getLogger(__name__)

class GeminiProvider(BaseAIProvider):
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
        self.api_key = api_key
        
        # New SDK: Client initialization accepts the API key directly
        self.client = genai.Client(api_key=self.api_key)
        # Upgraded to modern 2026/2027 standard default model 
        self.default_model = "gemini-2.5-flash"
        
    def generate_content(self, prompt: str, **kwargs) -> str:
        max_retries = kwargs.get("max_retries", 3)
        backoff_factor = kwargs.get("backoff_factor", 2.0)
        initial_delay = kwargs.get("initial_delay", 1.0)
        model_name = kwargs.get("model", self.default_model)
        
        # Extract config params from kwargs
        system_instruction = kwargs.get("system_instruction", None)
        response_mime_type = kwargs.get("response_mime_type", None)
        response_schema = kwargs.get("response_schema", None)
        
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=kwargs.get("temperature", 0.3),
            response_mime_type=response_mime_type,
            response_schema=response_schema
        )

        delay = initial_delay
        for attempt in range(max_retries + 1):
            try:
                # New SDK syntax: client.models.generate_content
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config
                )
                
                if response.text:
                    return response.text
                raise Exception("Gemini response did not contain text content.")
                
            except Exception as e:
                err_msg = str(e)
                # Check for rate limiting / temporary server errors
                is_rate_limit = any(term in err_msg for term in ["429", "ResourceExhausted", "Quota", "quota"])
                is_server_error = any(term in err_msg for term in ["500", "503", "ServiceUnavailable", "InternalServerError"])
                
                if (is_rate_limit or is_server_error) and attempt < max_retries:
                    logger.warning(
                        f"Gemini API call failed on attempt {attempt + 1}: {err_msg}. "
                        f"Retrying in {delay} seconds..."
                    )
                    time.sleep(delay)
                    delay *= backoff_factor
                else:
                    logger.error(f"Gemini API call failed permanently on attempt {attempt + 1}: {err_msg}")
                    raise e
                    
        raise Exception("Failed to generate content after retries.")
