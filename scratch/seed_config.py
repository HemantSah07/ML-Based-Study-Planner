import sys
sys.path.insert(0, '.')
from app import create_app, db
from app.models import AppSetting
from config import Config

app = create_app()
with app.app_context():
    # Create the table
    db.create_all()
    print("Database tables ensured.")
    
    # Define settings to seed
    default_settings = [
        {"key": "GEMINI_API_KEY", "value": Config.GEMINI_API_KEY or "", "description": "Google Gemini API Key"},
        {"key": "ANTHROPIC_API_KEY", "value": Config.ANTHROPIC_API_KEY or "", "description": "Anthropic API Key"},
        {"key": "GEMINI_MODEL_MCQ", "value": Config.GEMINI_MODEL_MCQ or "gemini-3.1-flash-lite", "description": "Gemini Model for MCQ generation"},
        {"key": "GEMINI_MODEL_ASSISTANT_PRIMARY", "value": Config.GEMINI_MODEL_ASSISTANT_PRIMARY or "gemini-2.5-flash", "description": "Primary Gemini Model for AI Assistant"},
        {"key": "GEMINI_MODEL_ASSISTANT_FALLBACK", "value": Config.GEMINI_MODEL_ASSISTANT_FALLBACK or "gemini-2.5-flash-lite", "description": "Fallback Gemini Model for AI Assistant"},
        {"key": "GEMINI_DAILY_LIMIT_MCQ", "value": str(Config.GEMINI_DAILY_LIMIT_MCQ), "description": "Daily request limit for MCQ generation"},
        {"key": "GEMINI_RPM_LIMIT_MCQ", "value": str(Config.GEMINI_RPM_LIMIT_MCQ), "description": "Requests Per Minute limit for MCQ generation"},
        {"key": "GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY", "value": str(Config.GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY), "description": "Daily request limit for Primary AI Assistant"},
        {"key": "GEMINI_DAILY_LIMIT_ASSISTANT_FALLBACK", "value": str(Config.GEMINI_DAILY_LIMIT_ASSISTANT_FALLBACK), "description": "Daily request limit for Fallback AI Assistant"},
        {"key": "GEMINI_RPM_LIMIT_ASSISTANT_PRIMARY", "value": str(Config.GEMINI_RPM_LIMIT_ASSISTANT_PRIMARY), "description": "Requests Per Minute limit for Primary AI Assistant"},
        {"key": "GEMINI_BILLING_ENABLED", "value": "True" if Config.GEMINI_BILLING_ENABLED else "False", "description": "Flag to bypass daily usage limits"},
    ]
    
    seeded_count = 0
    for s in default_settings:
        existing = AppSetting.query.get(s["key"])
        if not existing:
            new_s = AppSetting(
                key=s["key"],
                value=s["value"],
                description=s["description"]
            )
            db.session.add(new_s)
            seeded_count += 1
            
    db.session.commit()
    print(f"Seeded {seeded_count} configurations.")
