import sys; sys.path.insert(0,'.')
from app import create_app, db
from sqlalchemy import inspect

app = create_app()
with app.app_context():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print("Tables:", tables)
    # Check for chapter and MCQ tables specifically
    for t in tables:
        if any(kw in t.lower() for kw in ['chapter', 'mcq', 'question', 'quiz', 'content']):
            cols = [c['name'] for c in inspector.get_columns(t)]
            print(f"  {t}: {cols}")
