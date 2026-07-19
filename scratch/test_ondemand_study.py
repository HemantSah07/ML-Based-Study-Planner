import os
import sys
# Set pythonpath
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db
from app.models import Subject, Chapter, Topic, LearningMaterial
from app.services.ai_service import ai_service

app = create_app()
with app.app_context():
    # Let's inspect Subject 346
    subject = Subject.query.get(346)
    print(f"Testing subject: {subject.name}")
    
    # Check chapters
    chapters = Chapter.query.filter_by(subject_id=subject.id).all()
    print(f"Initial chapters count: {len(chapters)}")
    
    if not chapters:
        print("No chapters. Generating...")
        try:
            chapters = ai_service.generate_chapters_for_subject(subject.id)
            print(f"Generated {len(chapters)} chapters!")
            for c in chapters:
                print(f" - Chapter {c.chapter_number}: {c.name}")
        except Exception as e:
            print(f"Failed to generate chapters: {e}")
            sys.exit(1)
            
    # Now let's test generating topics for the first chapter
    if chapters:
        first_ch = chapters[0]
        topics = Topic.query.filter_by(chapter_id=first_ch.id).all()
        print(f"Initial topics count for Chapter {first_ch.chapter_number}: {len(topics)}")
        
        if not topics:
            print("No topics. Generating...")
            try:
                topics = ai_service.generate_topics_for_chapter(first_ch.id)
                print(f"Generated {len(topics)} topics!")
                for t in topics:
                    print(f"  * Topic {t.topic_number}: {t.name}")
            except Exception as e:
                print(f"Failed to generate topics: {e}")
                sys.exit(1)
                
    print("On-demand verification completed successfully.")
