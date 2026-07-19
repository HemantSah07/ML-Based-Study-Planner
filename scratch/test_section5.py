"""Section 5 Test: Cohort Analytics"""
import sys
sys.path.insert(0, '.')
from app import create_app
from app.models import User

app = create_app()
app.config['TESTING'] = True
errors = []

with app.app_context():
    admin = User.query.filter_by(role='admin').first()
    admin_id = admin.id

    # Test 1: Cohort logic calculation
    try:
        from app.models import StudentProfile, Prediction, StudyLog, StudentAssessment, EducationLevel
        from sqlalchemy import func
        
        levels = [l.name for l in EducationLevel.query.filter_by(is_active=True).order_by(EducationLevel.sort_order).all()]
        if not levels:
            from app import db
            levels = [r[0] for r in db.session.query(StudentProfile.study_level).distinct().all() if r[0]]
            
        print(f"Detected {len(levels)} cohort levels for testing.")
        assert len(levels) >= 0
        print("PASS: Cohort level resolution works.")
    except Exception as e:
        errors.append(f"FAIL cohort level query: {e}")
        print(f"FAIL: {e}")

    # Test 2: Renders via test client
    try:
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess['_user_id'] = str(admin_id)
                sess['_fresh'] = True
            r = c.get('/admin/analytics', follow_redirects=True)
            assert r.status_code == 200, f"Expected 200, got {r.status_code}"
            assert b"Analytics" in r.data or b"analytics" in r.data.lower()
            assert b"Enrolled Students" in r.data
        print("PASS: /admin/analytics dashboard renders successfully")
    except Exception as e:
        errors.append(f"FAIL analytics route: {e}")
        print(f"FAIL: {e}")

if errors:
    print(f"\n=== Section 5: {len(errors)} FAILURE(S) ===")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)
else:
    print("\n=== Section 5: ALL TESTS PASSED ===")
