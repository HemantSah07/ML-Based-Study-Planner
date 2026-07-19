from app import create_app, db
from app.models import User, Subject, StudentSubject, StudentProfile

app = create_app()
with app.app_context():
    user = User.query.filter_by(email='hemant@study.lbef.edu.np').first()
    if user:
        profile = StudentProfile.query.filter_by(user_id=user.id).first()
        print(f"User: {user.full_name}, Email: {user.email}, Role: {user.role}")
        print(f"Profile: student_number: {profile.student_number}, study_level: {profile.study_level}, curriculum: {profile.curriculum}")
        
        subjects = StudentSubject.query.filter_by(user_id=user.id).all()
        print("Active Student Subjects:")
        for s in subjects:
            subj = Subject.query.get(s.subject_id)
            print(f"- Subject ID: {subj.id}, Name: {subj.name}, Code: {subj.code}, Program: {subj.program}, Level: {subj.level_of_study}")
            
        print("\nSearching database for BE Computer Core I subject:")
        be_subjects = Subject.query.filter(Subject.name.like('%BE Computer Core%')).all()
        for subj in be_subjects:
            print(f"- Subject ID: {subj.id}, Name: {subj.name}, Code: {subj.code}, Program: {subj.program}, Level: {subj.level_of_study}")
    else:
        print("User hemant@study.lbef.edu.np not found!")
