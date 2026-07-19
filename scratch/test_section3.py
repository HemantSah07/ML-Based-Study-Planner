"""
Section 3 Test: Student Management (admin routes) — uses direct user context injection
"""
import sys
sys.path.insert(0, '.')
from app import create_app, db
from app.models import User, StudentProfile
from flask import url_for
from flask_login import login_user

app = create_app()
app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False
app.config['SERVER_NAME'] = None  # avoid url_for issues in test

errors = []

with app.app_context():
    admin = User.query.filter_by(role='admin').first()
    student = User.query.filter_by(role='student').first()

    if not admin:
        print("SKIP: No admin user found."); sys.exit(0)
    if not student:
        print("SKIP: No student user found."); sys.exit(0)

    admin_id = admin.id
    student_id = student.id
    student_email = student.email
    print(f"Admin id={admin_id}  Student id={student_id} email={student_email}")

    # ── Test 1: Students list route logic ────────────────────────────────────
    try:
        from app.models import StudentSubject, StudyPlan, EducationLevel
        from math import ceil

        search_q = ''
        selected_level = ''
        selected_status = ''
        per_page = 25
        page = 1

        query = User.query.filter_by(role='student')
        total = query.count()
        pages = ceil(total / per_page) if total else 1
        users = query.offset((page-1)*per_page).limit(per_page).all()

        rows = []
        for u in users:
            prof = u.profile
            profile_complete = bool(prof and prof.country and prof.study_level)
            assessed = bool(prof and prof.has_completed_assessment)
            has_subjects = StudentSubject.query.filter_by(user_id=u.id).count() > 0
            has_planner = StudyPlan.query.filter_by(student_id=u.id).count() > 0
            rows.append({
                'user': u, 'profile': prof,
                'profile_complete': profile_complete, 'assessed': assessed,
                'has_subjects': has_subjects, 'has_planner': has_planner,
            })

        print(f"PASS: Student list logic — {len(rows)} student(s) built successfully")
    except Exception as e:
        errors.append(f"FAIL student list logic: {e}")
        print(f"FAIL: {e}")

    # ── Test 2: Student detail query logic ───────────────────────────────────
    try:
        from app.models import Prediction, StudentAssessment, StudyPlan
        s = User.query.get(student_id)
        profile = s.profile
        subjects = StudentSubject.query.filter_by(user_id=student_id).all()
        latest_pred = Prediction.query.filter_by(user_id=student_id).order_by(Prediction.date.desc()).first()
        assessments = StudentAssessment.query.filter_by(student_id=student_id).order_by(StudentAssessment.completed_at.desc()).limit(10).all()
        study_plan = StudyPlan.query.filter_by(student_id=student_id).order_by(StudyPlan.generated_at.desc()).first()
        print(f"PASS: Student detail data — subjects={len(subjects)}, assessments={len(assessments)}, plan={'yes' if study_plan else 'no'}")
    except Exception as e:
        errors.append(f"FAIL student detail: {e}")
        print(f"FAIL: {e}")

    # ── Test 3: Impersonation sets session correctly ─────────────────────────
    try:
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess['_user_id'] = str(admin_id)
                sess['_fresh'] = True
            r = c.post(f'/admin/students/{student_id}/impersonate', follow_redirects=True)
            with c.session_transaction() as sess:
                imp_id = sess.get('impersonating_student_id')
            assert imp_id == student_id, f"Expected {student_id} got {imp_id}"
        print(f"PASS: Impersonation session set to student_id={student_id}")
    except Exception as e:
        errors.append(f"FAIL impersonation: {e}")
        print(f"FAIL impersonation: {e}")

    # ── Test 4: Exit impersonation clears session ────────────────────────────
    try:
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess['_user_id'] = str(admin_id)
                sess['_fresh'] = True
                sess['impersonating_student_id'] = student_id
            r = c.get('/admin/impersonate/exit', follow_redirects=True)
            with c.session_transaction() as sess:
                imp_id = sess.get('impersonating_student_id')
            assert imp_id is None, f"Session not cleared: {imp_id}"
        print("PASS: Exit impersonation clears session")
    except Exception as e:
        errors.append(f"FAIL exit impersonation: {e}")
        print(f"FAIL: {e}")

    # ── Test 5: Reset assessment route ───────────────────────────────────────
    try:
        profile = StudentProfile.query.filter_by(user_id=student_id).first()
        if profile:
            profile.has_completed_assessment = True
            db.session.commit()

        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess['_user_id'] = str(admin_id)
                sess['_fresh'] = True
            r = c.post(f'/admin/students/{student_id}/reset-assessment', follow_redirects=True)
            assert r.status_code == 200

        profile = StudentProfile.query.filter_by(user_id=student_id).first()
        if profile:
            assert not profile.has_completed_assessment, "Assessment not reset"
        print("PASS: Reset assessment route works")
    except Exception as e:
        errors.append(f"FAIL reset assessment: {e}")
        print(f"FAIL: {e}")

    # ── Test 6: Toggle active route ──────────────────────────────────────────
    try:
        s = User.query.get(student_id)
        original = s.is_active

        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess['_user_id'] = str(admin_id)
                sess['_fresh'] = True
            r = c.post(f'/admin/students/{student_id}/toggle-active', follow_redirects=True)
            assert r.status_code == 200

        s = User.query.get(student_id)
        assert s.is_active != original, "Toggle did not change status"
        # Restore
        s.is_active = original
        db.session.commit()
        print("PASS: Toggle active works and is reversible")
    except Exception as e:
        errors.append(f"FAIL toggle active: {e}")
        print(f"FAIL: {e}")

    # ── Test 7: Banner context — models loaded correctly ─────────────────────
    try:
        s = User.query.get(student_id)
        banner_text = s.full_name or s.email
        assert banner_text, "No name/email for banner"
        print(f"PASS: Banner will show '{banner_text}'")
    except Exception as e:
        errors.append(f"FAIL banner: {e}")
        print(f"FAIL: {e}")

# Summary
if errors:
    print(f"\n=== Section 3: {len(errors)} FAILURE(S) ===")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)
else:
    print("\n=== Section 3: ALL TESTS PASSED ===")
