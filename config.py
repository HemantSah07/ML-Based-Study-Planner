import os
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "SmartStudy@APU2025#NP069826")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
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
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(basedir, 'smart_study.db')}"
    
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

