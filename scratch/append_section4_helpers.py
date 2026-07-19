"""
Append Section 4: System Health Dashboard — replaces stub route
"""

section4_code = '''

# ── SECTION 4: SYSTEM HEALTH DASHBOARD ───────────────────────────────────────
import os, time, sys
from flask import current_app

# Replace the stub
# (the stub exists from append_stubs.py; Flask will use the LAST registered
#  route for duplicates, but to be safe we'll use a new internal function
#  and route this under /admin/health which the blueprint already has stubs for)


def _check_gemini_api():
    """Ping Gemini with a minimal token to verify the API key is live."""
    try:
        api_key = current_app.config.get("GEMINI_API_KEY", "")
        if not api_key:
            return {"status": "unconfigured", "latency_ms": None, "detail": "No API key set"}
        try:
            from google import genai as _genai
            client = _genai.Client(api_key=api_key)
            start = time.perf_counter()
            resp = client.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents="Reply with exactly: OK",
            )
            latency = round((time.perf_counter() - start) * 1000)
            text = getattr(resp, "text", "") or ""
            return {"status": "ok", "latency_ms": latency, "detail": text.strip()[:80]}
        except ImportError:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.0-flash-lite")
            start = time.perf_counter()
            resp = model.generate_content("Reply with exactly: OK")
            latency = round((time.perf_counter() - start) * 1000)
            return {"status": "ok", "latency_ms": latency, "detail": (resp.text or "")[:80]}
    except Exception as e:
        return {"status": "error", "latency_ms": None, "detail": str(e)[:120]}


def _check_ml_model():
    """Check that the Random Forest model and scaler are loadable."""
    try:
        from app.routes.student import load_ml_model
        model = load_ml_model("random_forest")
        scaler = load_ml_model("scaler")
        if model and scaler:
            return {"status": "ok", "detail": f"RF model: {type(model).__name__}, Scaler: {type(scaler).__name__}"}
        return {"status": "missing", "detail": "Model or scaler not found — train ML first"}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:120]}


def _check_db():
    """Verify database is reachable and return table row counts."""
    try:
        start = time.perf_counter()
        student_count = User.query.filter_by(role="student").count()
        latency = round((time.perf_counter() - start) * 1000)
        pred_count = Prediction.query.count()
        return {"status": "ok", "latency_ms": latency, "detail": f"Students: {student_count}, Predictions: {pred_count}"}
    except Exception as e:
        return {"status": "error", "latency_ms": None, "detail": str(e)[:120]}


def _get_model_config():
    """Return a dict of model config for display."""
    cfg = current_app.config
    return [
        {"label": "MCQ Generator", "model": cfg.get("GEMINI_MODEL_MCQ", "—"), "daily_limit": cfg.get("GEMINI_DAILY_LIMIT_MCQ", "—"), "rpm": cfg.get("GEMINI_RPM_LIMIT_MCQ", "—")},
        {"label": "AI Assistant (Primary)", "model": cfg.get("GEMINI_MODEL_ASSISTANT_PRIMARY", "—"), "daily_limit": cfg.get("GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY", "—"), "rpm": cfg.get("GEMINI_RPM_LIMIT_ASSISTANT_PRIMARY", "—")},
        {"label": "AI Assistant (Fallback)", "model": cfg.get("GEMINI_MODEL_ASSISTANT_FALLBACK", "—"), "daily_limit": cfg.get("GEMINI_DAILY_LIMIT_ASSISTANT_FALLBACK", "—"), "rpm": "—"},
    ]


def _get_disk_info():
    try:
        import shutil
        total, used, free = shutil.disk_usage("/")
        return {
            "total_gb": round(total / 1e9, 1),
            "used_gb": round(used / 1e9, 1),
            "free_gb": round(free / 1e9, 1),
            "pct_used": round(used / total * 100, 1),
        }
    except Exception:
        return {}


def _get_python_info():
    return {
        "version": sys.version.split(" ")[0],
        "executable": sys.executable,
        "platform": sys.platform,
    }

'''

with open('app/routes/admin.py', 'a', encoding='utf-8') as f:
    f.write(section4_code)

print("SUCCESS: Section 4 helpers appended")
