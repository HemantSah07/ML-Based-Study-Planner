"""Section 2 Test: Content Management routes and templates"""
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

    # Test 1: content_stats logic
    try:
        from app.models import Subject as SubjectModel, AssessmentQuestion
        from sqlalchemy import inspect
        from app import db
        inspector = inspect(db.engine)

        subjects = SubjectModel.query.order_by(SubjectModel.name).all()
        rows = []
        for s in subjects:
            from app.models import Chapter
            ch_count = Chapter.query.filter_by(subject_id=s.id).count()
            q_count = AssessmentQuestion.query.filter_by(subject_id=s.id).count()
            rows.append({"subject": s, "chapters": ch_count, "questions": q_count})
        total_questions = AssessmentQuestion.query.count()
        print(f"PASS: Content stats — {len(subjects)} subjects, {total_questions} total MCQs")
    except Exception as e:
        errors.append(f"FAIL content stats: {e}")
        print(f"FAIL: {e}")

    # Test 2: content routes render via test client
    for route, label in [
        ('/admin/content', 'content_subjects->redirect->stats'),
        ('/admin/content/stats', 'content_stats'),
        ('/admin/content/chapters', 'content_chapters'),
        ('/admin/content/questions', 'content_questions'),
    ]:
        try:
            with app.test_client() as c:
                with c.session_transaction() as sess:
                    sess['_user_id'] = str(admin_id)
                    sess['_fresh'] = True
                r = c.get(route, follow_redirects=True)
                assert r.status_code == 200, f"Expected 200 got {r.status_code}"
            print(f"PASS: {route} ({label}) returns 200")
        except Exception as e:
            errors.append(f"FAIL {route}: {e}")
            print(f"FAIL {route}: {e}")

    # Test 3: AssessmentQuestion has subject relationship
    try:
        from app.models import AssessmentQuestion
        q = AssessmentQuestion.query.first()
        if q:
            # Try accessing relationship
            subj = q.subject
            print(f"PASS: AssessmentQuestion.subject relationship works (subject={'yes' if subj else 'no'})")
        else:
            print("SKIP: No questions in DB to test relationship")
    except Exception as e:
        errors.append(f"FAIL AssessmentQuestion.subject: {e}")
        print(f"FAIL: {e}")

if errors:
    print(f"\n=== Section 2: {len(errors)} FAILURE(S) ===")
    for e in errors: print(f"  {e}")
    sys.exit(1)
else:
    print("\n=== Section 2: ALL TESTS PASSED ===")
