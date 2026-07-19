from app import create_app, db
from app.models import User, StudentProfile
from app.routes.student import get_profile_subjects

app = create_app()
with app.app_context():
    user = User.query.filter_by(email='hemant@study.lbef.edu.np').first()
    profile = StudentProfile.query.filter_by(user_id=user.id).first()
    active = get_profile_subjects(profile)
    print("get_profile_subjects returned:")
    for a in active:
        print(f"- ID: {a.id}, Name: {a.name}")
