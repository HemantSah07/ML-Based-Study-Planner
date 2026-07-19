from app import create_app
from app.models import AICache
import re
import json

app = create_app()
with app.app_context():
    cache = AICache.query.filter_by(prompt_hash='16c6904707ccccd7611ad0ee4dc73f371319851625e459cd2acd9d80870982ee').first()
    if cache:
        text = cache.response_text
        print("Total length:", len(text))
        
        # Count raw occurrences of "q": 
        q_matches = re.findall(r'"q":', text)
        print("Raw 'q': matches count:", len(q_matches))
        
        # Let's inspect where it gets cut off or what is happening
        # Try to parse it with a lenient parser or print the first 2000 chars of text
        print("Start of response text:")
        print(text[:2000])
        print("End of response text:")
        print(text[-2000:])
