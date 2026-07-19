"""
test_section6.py
Automated validation of Section 6: Access Control & Security.
- Verifies that student role redirects to student dashboard in before_request.
- Performs an admin action and verifies that it is logged in AdminActivityLog.
"""
from app import create_app, db
from app.models import User, AdminActivityLog
from flask_login import login_user
from app.routes.admin import require_admin, log_admin_action

app = create_app()

with app.app_context():
    print("=== RUNNING SECTION 6 TESTS ===")
    
    # 1. Setup/get an admin user and a student user for the test
    admin_user = User.query.filter_by(role="admin").first()
    student_user = User.query.filter_by(role="student").first()
    
    if not admin_user:
        admin_user = User(email="admin_test_sec6@test.com", role="admin", password_hash="hash")
        db.session.add(admin_user)
        db.session.commit()
        print(f"Created temp admin user: {admin_user.email}")
        
    if not student_user:
        student_user = User(email="student_test_sec6@test.com", role="student", password_hash="hash")
        db.session.add(student_user)
        db.session.commit()
        print(f"Created temp student user: {student_user.email}")

    # 2. Test require_admin before-request hook directly
    # Student user
    with app.test_request_context():
        login_user(student_user)
        res = require_admin()
        assert res is not None, "require_admin should return redirect for student!"
        assert res.status_code == 302, "Expected 302 redirect"
        assert "/student" in res.headers["Location"], f"Expected redirect to student dashboard, got {res.headers['Location']}"
        print("   Verified: require_admin blocks student user and redirects to student path.")

    # Admin user
    with app.test_request_context():
        login_user(admin_user)
        res = require_admin()
        assert res is None, "require_admin should allow admin to proceed (return None)!"
        print("   Verified: require_admin allows admin user to proceed.")

    # 3. Test administrative action logging
    with app.test_request_context():
        login_user(admin_user)
        test_detail = "Test action performed via automated test suite"
        log_admin_action(
            action="test_suite_action",
            entity_type="TestModel",
            entity_id=999,
            detail=test_detail
        )
        
        # Query recent logs
        recent_log = AdminActivityLog.query.filter_by(action="test_suite_action").order_by(AdminActivityLog.timestamp.desc()).first()
        assert recent_log is not None, "Log record was not saved!"
        assert recent_log.admin_user_id == admin_user.id, "Log must be associated with the logged-in admin user!"
        assert recent_log.detail == test_detail, f"Expected detail to be '{test_detail}', got '{recent_log.detail}'"
        print("   Verified: Admin activity log record was successfully created and verified.")

        # Clean up
        db.session.delete(recent_log)
        db.session.commit()

    # Clean up temp users if created
    if admin_user.email == "admin_test_sec6@test.com":
        db.session.delete(admin_user)
    if student_user.email == "student_test_sec6@test.com":
        db.session.delete(student_user)
    db.session.commit()
    print("4. Cleaned up temporary test users.")
    print("=== SECTION 6 TESTS PASSED SUCCESSFULLY ===")
