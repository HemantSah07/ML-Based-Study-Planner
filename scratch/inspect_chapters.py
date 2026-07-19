from app import create_app, db
from app.models import Subject, Chapter, Topic

app = create_app()
with app.app_context():
    subj = Subject.query.get(346)
    print(f"Subject: {subj.name if subj else 'None'}")
    if subj:
        chapters = Chapter.query.filter_by(subject_id=subj.id).all()
        print(f"Number of chapters: {len(chapters)}")
        for ch in chapters:
            topics = Topic.query.filter_by(chapter_id=ch.id).all()
            print(f"- Chapter: {ch.chapter_number}. {ch.name} ({len(topics)} topics)")
            for t in topics:
                print(f"  * Topic: {t.topic_number}. {t.name}")
