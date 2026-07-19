from app import create_app, db
from app.models import User, Subject, StudentSubject, StudentProfile

app = create_app()
with app.app_context():
    profile = StudentProfile.query.filter_by(student_number='NP069826').first()
    if profile:
        user = User.query.get(profile.user_id)
        print(f"Profile student_number NP069826 belongs to User ID: {profile.user_id}")
        if user:
            print(f"User email: {user.email}, Name: {user.full_name}, study_level: {profile.study_level}")
        else:
            print("User record not found for this profile!")
    else:
        print("Profile not found by student_number NP069826")
        
    print("\nListing all users:")
    for u in User.query.all():
        p = StudentProfile.query.filter_by(user_id=u.id).first()
        print(f"- ID: {u.id}, Name: {u.full_name}, Email: {u.email}, Role: {u.role}, Profile student_number: {p.student_number if p else 'None'}, study_level: {p.study_level if p else 'None'}")
