import os
import sys
import time
import logging

# Ensure root dir is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set up logging to console
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("app.services.ai_service")
logger.setLevel(logging.INFO)

from app.services.ai_service import ai_service

def test_json_correction():
    print("\n" + "="*50)
    print("TEST 1: Malformed JSON (Missing Comma) & Self-Correction")
    print("="*50)
    
    calls = []
    def mock_generate_content(prompt, **kwargs):
        calls.append(prompt)
        # First call returns malformed JSON (missing comma between "a" and "b")
        if len(calls) == 1:
            return '{"q": "What is 2+2?", "a": "4" "b": "5", "ans": "A", "exp": "Basic math. This is a very long explanation intended to ensure that the content length exceeds the 100 characters threshold required by the validation system."}'
        # Correction call returns valid JSON
        return '{"q": "What is 2+2?", "a": "4", "b": "5", "ans": "A", "exp": "Basic math. This is a very long explanation intended to ensure that the content length exceeds the 100 characters threshold required by the validation system."}'
        
    ai_service.generate_content = mock_generate_content
    
    try:
        result = ai_service.call_gemini_reusable(
            prompt="Dummy prompt",
            feature="mcq",
            is_json=True,
            context="test_json_correction"
        )
        print("Result:", result)
        print("Number of generate_content calls:", len(calls))
        assert len(calls) == 2, "Should have made 2 calls (initial + correction)"
        assert result["a"] == "4", "Parsed corrected JSON is incorrect"
        print("TEST 1 PASSED!")
    except Exception as e:
        print("TEST 1 FAILED:", e)

def test_429_retry():
    print("\n" + "="*50)
    print("TEST 2: Simulate 429/ResourceExhausted Error & Retries")
    print("="*50)
    
    calls_count = 0
    def mock_generate_content(prompt, **kwargs):
        nonlocal calls_count
        calls_count += 1
        if calls_count < 3:
            # Simulate Gemini API Rate Limit Exception
            raise Exception("API error status: 429. ResourceExhausted: Quota exceeded.")
        # Success on 3rd attempt
        return "This is a valid response that is long enough to pass length validation. It has headings:\n## Heading 1\nContent content content."
        
    ai_service.generate_content = mock_generate_content
    
    try:
        t0 = time.time()
        result = ai_service.call_gemini_reusable(
            prompt="Dummy prompt",
            feature="assistant",
            is_json=False,
            check_headings=True,
            context="test_429_retry"
        )
        elapsed = time.time() - t0
        print("Result:", result)
        print("Number of generate_content attempts:", calls_count)
        print(f"Elapsed time (should be ~4 seconds due to 1s + 3s delays): {elapsed:.2f}s")
        assert calls_count == 3, "Should have attempted 3 times"
        assert elapsed >= 4.0, "Should have slept for 1s + 3s"
        print("TEST 2 PASSED!")
    except Exception as e:
        print("TEST 2 FAILED:", e)

def test_validation_rejection():
    print("\n" + "="*50)
    print("TEST 3: Short Response (< 100 chars) & No Headings Rejection")
    print("="*50)
    
    def mock_generate_content(prompt, **kwargs):
        # Short response under 100 characters with no headings
        return "Too short"
        
    ai_service.generate_content = mock_generate_content
    
    try:
        ai_service.call_gemini_reusable(
            prompt="Dummy prompt",
            feature="assistant",
            is_json=False,
            check_headings=True,
            context="test_validation_rejection"
        )
        print("TEST 3 FAILED: Short response was not rejected!")
    except ValueError as e:
        print("Caught expected validation exception:", e)
        print("TEST 3 PASSED!")

if __name__ == "__main__":
    test_json_correction()
    test_429_retry()
    test_validation_rejection()
