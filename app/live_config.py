import time
from flask import current_app

_config_cache = {}
_config_last_loaded = 0.0

def load_live_config(app, force=False):
    global _config_last_loaded, _config_cache
    now = time.time()
    if force or (now - _config_last_loaded > 60):
        from app.models import AppSetting
        try:
            settings = AppSetting.query.all()
            for s in settings:
                val = s.value
                # Parse to appropriate types
                if s.key == "GEMINI_BILLING_ENABLED":
                    val = val.lower() in ("true", "1", "yes")
                elif s.key in (
                    "GEMINI_DAILY_LIMIT_MCQ", 
                    "GEMINI_RPM_LIMIT_MCQ", 
                    "GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY", 
                    "GEMINI_DAILY_LIMIT_ASSISTANT_FALLBACK", 
                    "GEMINI_RPM_LIMIT_ASSISTANT_PRIMARY"
                ):
                    try:
                        val = int(val)
                    except (ValueError, TypeError):
                        val = 0
                app.config[s.key] = val
            _config_last_loaded = now
        except Exception as e:
            # Table might not exist yet during migrations/initialization
            pass
