from app import create_app, db
from app.models import User, StudentProfile, StudentSubject, Subject

app = create_app()

with app.app_context():
    user = User.query.filter_by(email='hemant@study.lbef.edu.np').first()
    if user:
        profile = StudentProfile.query.filter_by(user_id=user.id).first()
        profile.study_level = "Bachelors"
        profile.program = "BE Computer"
        
        # 3. Add subjects if not exists
        for sub_id in [346, 347, 348]:
            exist = StudentSubject.query.filter_by(user_id=user.id, subject_id=sub_id).first()
            if not exist:
                ss = StudentSubject(user_id=user.id, subject_id=sub_id)
                db.session.add(ss)
                print(f"Added subject {sub_id} to student")
            else:
                print(f"Subject {sub_id} already active for student")
                
        db.session.commit()
        print("Setup completed successfully!")
        
        # Let's also print valid subjects to verify
        from app.routes.student import get_valid_subjects_for_profile
        valid = get_valid_subjects_for_profile(profile)
        print("Valid subjects in profile context:")
        for v in valid:
            print(f"- ID: {v.id}, Name: {v.name}")
    else:
        print("User not found!")
