"""Section 8 Test: Bulk Operations Dashboard"""
import sys
sys.path.insert(0, '.')
from app import create_app, db
from app.models import User, Notification, StudentProfile, Prediction

app = create_app()
app.config['TESTING'] = True
errors = []

with app.app_context():
    admin = User.query.filter_by(role='admin').first()
    admin_id = admin.id
    student = User.query.filter_by(role='student').first()
    
    if not student:
        print("SKIP: No students found to test notifications.")
        sys.exit(0)
        
    student_id = student.id
    profile = student.profile
    cohort = profile.study_level if profile else None

    # Test 1: Batch ML execution logic
    try:
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess['_user_id'] = str(admin_id)
                sess['_fresh'] = True
            r = c.post('/admin/bulk', data={'action': 'batch_ml'}, follow_redirects=True)
            assert r.status_code == 200
        print("PASS: Batch ML endpoint returns 200/302 and runs")
    except Exception as e:
        errors.append(f"FAIL batch ML trigger: {e}")
        print(f"FAIL: {e}")

    # Test 2: Bulk Notification (all students)
    try:
        initial_count = Notification.query.filter_by(user_id=student_id).count()
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess['_user_id'] = str(admin_id)
                sess['_fresh'] = True
            r = c.post('/admin/bulk', data={
                'action': 'bulk_notification',
                'target': 'all',
                'message': 'Test general alert message'
            }, follow_redirects=True)
            assert r.status_code == 200
        new_count = Notification.query.filter_by(user_id=student_id).count()
        assert new_count == initial_count + 1, f"Notification count mismatch: before={initial_count}, after={new_count}"
        print("PASS: Bulk notification delivered to all students")
    except Exception as e:
        errors.append(f"FAIL bulk notify all: {e}")
        print(f"FAIL: {e}")

    # Test 3: Bulk Notification targeting cohort
    if cohort:
        try:
            initial_count = Notification.query.filter_by(user_id=student_id).count()
            with app.test_client() as c:
                with c.session_transaction() as sess:
                    sess['_user_id'] = str(admin_id)
                    sess['_fresh'] = True
                r = c.post('/admin/bulk', data={
                    'action': 'bulk_notification',
                    'target': 'cohort',
                    'cohort': cohort,
                    'message': 'Test cohort alert message'
                }, follow_redirects=True)
                assert r.status_code == 200
            new_count = Notification.query.filter_by(user_id=student_id).count()
            assert new_count == initial_count + 1
            print(f"PASS: Bulk notification targeted cohort '{cohort}' successfully")
        except Exception as e:
            errors.append(f"FAIL bulk notify cohort: {e}")
            print(f"FAIL: {e}")
    else:
        print("SKIP: Student profile has no cohort to target.")

    # Test 4: Bulk Notification targeting risk level
    try:
        pred = Prediction.query.filter_by(user_id=student_id).order_by(Prediction.date.desc()).first()
        risk_lvl = (pred.predicted_risk_level or "low").lower() if pred else "low"
        
        initial_count = Notification.query.filter_by(user_id=student_id).count()
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess['_user_id'] = str(admin_id)
                sess['_fresh'] = True
            r = c.post('/admin/bulk', data={
                'action': 'bulk_notification',
                'target': 'risk',
                'risk_level': risk_lvl,
                'message': 'Test risk-level alert message'
            }, follow_redirects=True)
            assert r.status_code == 200
        new_count = Notification.query.filter_by(user_id=student_id).count()
        assert new_count == initial_count + 1
        print(f"PASS: Bulk notification targeted risk level '{risk_lvl}' successfully")
    except Exception as e:
        errors.append(f"FAIL bulk notify risk: {e}")
        print(f"FAIL: {e}")

if errors:
    print(f"\n=== Section 8: {len(errors)} FAILURE(S) ===")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)
else:
    print("\n=== Section 8: ALL TESTS PASSED ===")
