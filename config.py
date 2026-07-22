import os
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE-ME-IN-PRODUCTION-SET-SECRET-KEY-ENV-VAR")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Production Debug & Session Cookie Security Configuration
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() in ("true", "1", "yes")
    DEBUG = FLASK_DEBUG
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "True").lower() in ("true", "1", "yes")
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    
    # Check if configured for MySQL production or SQLite development
    DB_TYPE = os.getenv("DB_TYPE", "sqlite") # 'mysql' or 'sqlite'
    
    if DB_TYPE == "mysql":
        DB_USER = os.getenv("DB_USER", "root")
        DB_PASSWORD = os.getenv("DB_PASSWORD", "")
        DB_HOST = os.getenv("DB_HOST", "localhost")
        DB_NAME = os.getenv("DB_NAME", "smart_study")
        encoded_password = urllib.parse.quote_plus(DB_PASSWORD)
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{DB_USER}:{encoded_password}@{DB_HOST}/{DB_NAME}"
        )
    else:
        # SQLite local development database file
        basedir = os.path.abspath(os.path.dirname(__file__))
        db_file = os.path.join(basedir, 'smart_study.db').replace('\\', '/')
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_file}"

    
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    ABSTRACT_API_KEY = os.getenv("ABSTRACT_API_KEY")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

    # ── Gemini model selection per feature ────────────────────────────────────
    # Separate models give separate free-tier quota pools.
    # Change these to a paid-tier model name in .env when billing is enabled.
    GEMINI_MODEL_MCQ       = os.getenv("GEMINI_MODEL_MCQ",       "gemini-3.1-flash-lite")
    GEMINI_MODEL_ASSISTANT_PRIMARY = os.getenv("GEMINI_MODEL_ASSISTANT_PRIMARY", "gemini-2.5-flash")
    GEMINI_MODEL_ASSISTANT_FALLBACK = os.getenv("GEMINI_MODEL_ASSISTANT_FALLBACK", "gemini-2.5-flash-lite")

    # ── Usage limits (daily and RPM) ─────────────────────────────────────────
    GEMINI_DAILY_LIMIT_MCQ       = int(os.getenv("GEMINI_DAILY_LIMIT_MCQ",       "450"))
    GEMINI_RPM_LIMIT_MCQ         = int(os.getenv("GEMINI_RPM_LIMIT_MCQ",         "10"))

    GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY  = int(os.getenv("GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY",  "45"))
    GEMINI_DAILY_LIMIT_ASSISTANT_FALLBACK = int(os.getenv("GEMINI_DAILY_LIMIT_ASSISTANT_FALLBACK", "45"))
    GEMINI_RPM_LIMIT_ASSISTANT_PRIMARY   = int(os.getenv("GEMINI_RPM_LIMIT_ASSISTANT_PRIMARY",   "4"))

    # ── Billing switch ────────────────────────────────────────────────────────
    # Set GEMINI_BILLING_ENABLED=True in .env once a paid API key is active.
    # When True, the daily cap check is bypassed entirely — no other code
    # changes are needed at that point.
    GEMINI_BILLING_ENABLED = os.getenv("GEMINI_BILLING_ENABLED", "False").lower() in ("true", "1", "yes")

    # ── Flask-Mail configuration ──────────────────────────────────────────────
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "True").lower() in ("true", "1", "yes")
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_USERNAME")

