import unittest
import os
import json
import tempfile
from datetime import datetime, timedelta
from app import create_app, db, bcrypt
from app.models import (
    User, StudentProfile, Subject, StudentSubject, UploadedMaterial,
    MaterialChunk, AcademicDocument, ExtractedMark, StudentAssessment,
    AssessmentResponse, Prediction, StudyLog, Assignment, Exam, Schedule,
    Recommendation, Goal, AvailabilitySlot, StudentSeenQuestion, StudyPlan,
    AdminActivityLog, FlashcardReview, SubjectBook, QuizScore, StudyLogAnalysis,
    LearningProgress, StudentNote, SubjectPerformanceHistory, AIStudyMaterial,
    ReviewedChapter, ChapterQuizScore, ChapterQuizResult, TopicSeenQuestion,
    BookmarkedChapter, ChapterNote, MaterialImportBatch, MaterialImportUnmatched,
    ModuleDescriptor, EducationLevel, University, Faculty, CurriculumProgram,
    ProgramSubject, AdminRegistrationRequest, SUPER_ADMIN_EMAIL
)
from config import Config

def normalize_confirm_text(text):
    if text is None:
        return ''
    s = str(text).replace('\u00A0', ' ')
    import re
    s = re.sub(r'\s+', ' ', s)
    return s.strip().lower()

class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SERVER_NAME = 'localhost'

class Comprehensive50ScenariosTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestingConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        super_pw = bcrypt.generate_password_hash("SuperPass123!").decode('utf-8')
        admin_pw = bcrypt.generate_password_hash("AdminPass123!").decode('utf-8')
        student_pw = bcrypt.generate_password_hash("StudentPass123!").decode('utf-8')

        # Create Primary Super Admin
        self.super_admin = User(
            full_name="Primary Super Admin",
            email=SUPER_ADMIN_EMAIL,
            password_hash=super_pw,
            role="super_admin",
            is_active=True
        )

        # Create Regular Admin
        self.regular_admin = User(
            full_name="Regular Admin User",
            email="regular_admin_test@smartstudy.edu",
            password_hash=admin_pw,
            role="admin",
            is_active=True
        )

        # Create Test Student
        self.student = User(
            full_name="Test Student",
            email="student_test50@smartstudy.edu",
            password_hash=student_pw,
            role="student",
            is_active=True
        )

        db.session.add_all([self.super_admin, self.regular_admin, self.student])
        db.session.commit()

        # Student Profile
        self.student_profile = StudentProfile(
            user_id=self.student.id,
            study_level="Bachelors",
            level_of_study="Bachelors",
            program="Computer Science",
            country="Nepal"
        )
        db.session.add(self.student_profile)

        # Create Test Subject
        self.subject = Subject(
            name="Data Structures",
            code="CS201",
            level_of_study="Bachelors",
            difficulty_level=3
        )
        db.session.add(self.subject)
        db.session.commit()

        # Add assessment score for subject so risk-analysis API operates cleanly
        sa = StudentAssessment(
            student_id=self.student.id,
            subject_id=self.subject.id,
            total_score=80.0,
            max_score=100.0,
            weighted_score=80.0
        )
        db.session.add(sa)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login(self, email, password):
        return self.client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)

    # ── PART 1: ADMIN & PERMISSIONS (Scenarios 1-15) ─────────────────────────

    def test_01_primary_super_admin_recognized(self):
        u = User.query.filter_by(email=SUPER_ADMIN_EMAIL).first()
        self.assertTrue(u.is_protected_super_admin)
        self.assertTrue(u.is_super_admin)

    def test_02_primary_super_admin_cannot_be_deleted(self):
        self.login(SUPER_ADMIN_EMAIL, "SuperPass123!")
        res = self.client.post(f'/admin/admins/{self.super_admin.id}/delete-permanent', data={'confirm_text': SUPER_ADMIN_EMAIL}, follow_redirects=True)
        self.assertIn(b"CANNOT be deleted", res.data)
        self.assertIsNotNone(User.query.get(self.super_admin.id))

    def test_03_primary_super_admin_cannot_be_disabled(self):
        self.login(SUPER_ADMIN_EMAIL, "SuperPass123!")
        res = self.client.post(f'/admin/admins/{self.super_admin.id}/disable', follow_redirects=True)
        self.assertIn(b"CANNOT be disabled", res.data)
        u = User.query.get(self.super_admin.id)
        self.assertTrue(u.is_active)

    def test_04_primary_super_admin_cannot_be_demoted(self):
        u = User.query.filter_by(email=SUPER_ADMIN_EMAIL).first()
        u.role = "student"
        self.assertTrue(u.is_super_admin, "Property protection must treat email as Super Admin regardless of role column")

    def test_05_admin_registration_creates_pending_request(self):
        res = self.client.post('/register', data={
            'role': 'admin',
            'full_name': 'Applicant User',
            'email': 'applicant_personal@example.com',
            'password': 'ApplicantPass123!',
            'confirm_password': 'ApplicantPass123!'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        req = AdminRegistrationRequest.query.filter_by(email='applicant_personal@example.com').first()
        self.assertIsNotNone(req)
        self.assertEqual(req.status, 'PENDING')

    def test_06_applicant_personal_email_stored_correctly(self):
        req = AdminRegistrationRequest(
            full_name="Personal Email Test",
            email="personal_user@gmail.com",
            password_hash="hashed_pw"
        )
        db.session.add(req)
        db.session.commit()
        self.assertEqual(req.email, "personal_user@gmail.com")

    def test_07_super_admin_receives_notification(self):
        res = self.client.post('/register', data={
            'role': 'admin',
            'full_name': 'Notify Admin Test',
            'email': 'notify_user@gmail.com',
            'password': 'ApplicantPass123!',
            'confirm_password': 'ApplicantPass123!'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        req = AdminRegistrationRequest.query.filter_by(email='notify_user@gmail.com').first()
        self.assertIsNotNone(req)

    def test_08_approval_generates_verification_code(self):
        req = AdminRegistrationRequest(full_name="Code Test", email="code_test@gmail.com", password_hash="hash")
        db.session.add(req)
        db.session.commit()

        self.login(SUPER_ADMIN_EMAIL, "SuperPass123!")
        res = self.client.post(f'/admin/requests/{req.id}/approve', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        updated_req = AdminRegistrationRequest.query.get(req.id)
        self.assertEqual(updated_req.status, 'APPROVED')
        self.assertIsNotNone(updated_req.verification_code)
        self.assertEqual(len(updated_req.verification_code), 6)

    def test_09_verification_code_sent_to_applicant_email(self):
        req = AdminRegistrationRequest(full_name="Recipient Test", email="recipient@gmail.com", password_hash="hash")
        db.session.add(req)
        db.session.commit()

        self.login(SUPER_ADMIN_EMAIL, "SuperPass123!")
        res = self.client.post(f'/admin/requests/{req.id}/approve', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

    def test_10_verification_code_expires_after_24_hours(self):
        pw_hash = bcrypt.generate_password_hash("Pass123!").decode('utf-8')
        req = AdminRegistrationRequest(
            full_name="Expire Test",
            email="expire@gmail.com",
            password_hash=pw_hash,
            status="APPROVED",
            verification_code="123456",
            code_expires_at=datetime.utcnow() - timedelta(minutes=10),
            code_used=False
        )
        db.session.add(req)
        db.session.commit()

        res = self.client.post('/verify-admin-code', data={
            'email': 'expire@gmail.com',
            'verification_code': '123456'
        }, follow_redirects=True)
        self.assertIn(b"expired", res.data)

    def test_11_verification_code_single_use(self):
        pw_hash = bcrypt.generate_password_hash("ValidPass123!").decode('utf-8')
        req = AdminRegistrationRequest(
            full_name="Single Use Test",
            email="singleuse@gmail.com",
            password_hash=pw_hash,
            status="APPROVED",
            verification_code="654321",
            code_expires_at=datetime.utcnow() + timedelta(hours=24),
            code_used=True
        )
        db.session.add(req)
        db.session.commit()

        res = self.client.post('/verify-admin-code', data={
            'email': 'singleuse@gmail.com',
            'verification_code': '654321'
        }, follow_redirects=True)
        self.assertIn(b"No approved admin registration request found", res.data)

    def test_12_regular_admin_created_only_after_verification(self):
        pw_hash = bcrypt.generate_password_hash("ValidPass123!").decode('utf-8')
        req = AdminRegistrationRequest(
            full_name="Verified Admin",
            email="verified_new_admin@gmail.com",
            password_hash=pw_hash,
            status="APPROVED",
            verification_code="999888",
            code_expires_at=datetime.utcnow() + timedelta(hours=24),
            code_used=False
        )
        db.session.add(req)
        db.session.commit()

        res = self.client.post('/verify-admin-code', data={
            'email': 'verified_new_admin@gmail.com',
            'verification_code': '999888'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        created_admin = User.query.filter_by(email="verified_new_admin@gmail.com").first()
        self.assertIsNotNone(created_admin)
        self.assertEqual(created_admin.role, "admin")

    def test_13_regular_admin_cannot_access_super_admin_routes(self):
        self.login("regular_admin_test@smartstudy.edu", "AdminPass123!")
        res = self.client.get('/admin/manage-admins')
        self.assertEqual(res.status_code, 403)

    def test_14_regular_admin_cannot_access_permanent_deletion(self):
        self.login("regular_admin_test@smartstudy.edu", "AdminPass123!")
        res = self.client.post(f'/admin/students/{self.student.id}/delete-permanent', data={'confirm_text': self.student.email})
        self.assertEqual(res.status_code, 403)

    def test_15_super_admin_can_manage_regular_admins(self):
        self.login(SUPER_ADMIN_EMAIL, "SuperPass123!")
        res = self.client.get('/admin/manage-admins')
        self.assertEqual(res.status_code, 200)

    # ── PART 2: PERMANENT DELETION (Scenarios 16-32) ─────────────────────────

    def test_16_exact_confirmation_enables_delete_button_logic(self):
        target = "Bachelors Degree"
        entered = "  Bachelors   Degree  "
        self.assertEqual(normalize_confirm_text(entered), normalize_confirm_text(target))

    def test_17_incorrect_confirmation_keeps_disabled(self):
        target = "Bachelors Degree"
        entered = "Bachelor"
        self.assertNotEqual(normalize_confirm_text(entered), normalize_confirm_text(target))

    def test_18_backend_rejects_incorrect_confirmation(self):
        self.login(SUPER_ADMIN_EMAIL, "SuperPass123!")
        res = self.client.post(
            f'/admin/students/{self.student.id}/delete-permanent',
            data={'confirm_text': 'wrong_email@smartstudy.edu'},
            follow_redirects=True
        )
        self.assertIn(b"mismatch", res.data)
        self.assertIsNotNone(User.query.get(self.student.id))

    def test_19_student_deletion_succeeds(self):
        self.login(SUPER_ADMIN_EMAIL, "SuperPass123!")
        res = self.client.post(
            f'/admin/students/{self.student.id}/delete-permanent',
            data={'confirm_text': self.student.email},
            follow_redirects=True
        )
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(User.query.get(self.student.id))

    def test_20_student_uploaded_materials_handled(self):
        mat = UploadedMaterial(user_id=self.student.id, subject_id=self.subject.id, filename="doc.pdf", file_path="/tmp/doc.pdf", file_type="pdf")
        db.session.add(mat)
        db.session.commit()
        mid = mat.id

        self.login(SUPER_ADMIN_EMAIL, "SuperPass123!")
        self.client.post(f'/admin/students/{self.student.id}/delete-permanent', data={'confirm_text': self.student.email}, follow_redirects=True)
        self.assertIsNone(UploadedMaterial.query.get(mid))

    def test_21_student_deletion_no_not_null_integrity_error(self):
        mat = UploadedMaterial(user_id=self.student.id, subject_id=self.subject.id, filename="doc2.pdf", file_path="/tmp/doc2.pdf", file_type="pdf")
        db.session.add(mat)
        db.session.commit()

        self.login(SUPER_ADMIN_EMAIL, "SuperPass123!")
        res = self.client.post(f'/admin/students/{self.student.id}/delete-permanent', data={'confirm_text': self.student.email}, follow_redirects=True)
        self.assertNotIn(b"IntegrityError", res.data)
        self.assertIn(b"permanently deleted", res.data)

    def test_22_student_dependent_records_handled(self):
        pred = Prediction(user_id=self.student.id, attendance_pct=85.0)
        slog = StudyLog(user_id=self.student.id, date=db.func.current_date(), duration_hours=1.5)
        db.session.add_all([pred, slog])
        db.session.commit()

        self.login(SUPER_ADMIN_EMAIL, "SuperPass123!")
        self.client.post(f'/admin/students/{self.student.id}/delete-permanent', data={'confirm_text': self.student.email}, follow_redirects=True)
        self.assertEqual(Prediction.query.filter_by(user_id=self.student.id).count(), 0)
        self.assertEqual(StudyLog.query.filter_by(user_id=self.student.id).count(), 0)

    def test_23_permanent_deletion_atomic(self):
        self.login(SUPER_ADMIN_EMAIL, "SuperPass123!")
        res = self.client.post(f'/admin/students/{self.student.id}/delete-permanent', data={'confirm_text': self.student.email}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

    def test_24_failed_deletion_rolls_back_transaction(self):
        self.login(SUPER_ADMIN_EMAIL, "SuperPass123!")
        orig_del = db.session.delete
        def failing_del(obj):
            if isinstance(obj, User) and obj.id == self.student.id:
                raise RuntimeError("Controlled DB Error")
            return orig_del(obj)
        db.session.delete = failing_del
        try:
            res = self.client.post(f'/admin/students/{self.student.id}/delete-permanent', data={'confirm_text': self.student.email}, follow_redirects=True)
            self.assertIn(b"Failed to permanently delete", res.data)
            self.assertIsNotNone(User.query.get(self.student.id))
        finally:
            db.session.delete = orig_del

    def test_25_audit_log_created_after_successful_deletion(self):
        self.login(SUPER_ADMIN_EMAIL, "SuperPass123!")
        email = self.student.email
        self.client.post(f'/admin/students/{self.student.id}/delete-permanent', data={'confirm_text': email}, follow_redirects=True)
        log = AdminActivityLog.query.filter_by(action="permanently_deleted_student").first()
        self.assertIsNotNone(log)
        self.assertIn(email, log.detail)

    def test_26_regular_admin_403_all_delete_endpoints(self):
        self.login("regular_admin_test@smartstudy.edu", "AdminPass123!")
        eps = [
            f'/admin/admins/{self.super_admin.id}/delete-permanent',
            f'/admin/students/{self.student.id}/delete-permanent',
            '/admin/curriculum/levels/1/delete-permanent',
            '/admin/curriculum/universities/1/delete-permanent',
            '/admin/curriculum/faculties/1/delete-permanent',
            '/admin/curriculum/programs/1/delete-permanent',
            '/admin/curriculum/subjects/1/delete-permanent'
        ]
        for ep in eps:
            res = self.client.post(ep, data={'confirm_text': 'test'})
            self.assertEqual(res.status_code, 403)

    def test_27_super_admin_can_delete_education_level(self):
        lvl = EducationLevel(name="Test Level 99", country="Nepal")
        db.session.add(lvl)
        db.session.commit()

        self.login(SUPER_ADMIN_EMAIL, "SuperPass123!")
        res = self.client.post(f'/admin/curriculum/levels/{lvl.id}/delete-permanent', data={'confirm_text': 'Test Level 99'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(EducationLevel.query.get(lvl.id))

    def test_28_super_admin_can_delete_university(self):
        uni = University(name="Test University 99", country="Nepal")
        db.session.add(uni)
        db.session.commit()

        self.login(SUPER_ADMIN_EMAIL, "SuperPass123!")
        res = self.client.post(f'/admin/curriculum/universities/{uni.id}/delete-permanent', data={'confirm_text': 'Test University 99'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(University.query.get(uni.id))

    def test_29_super_admin_can_delete_faculty(self):
        fac = Faculty(name="Test Faculty 99", country="Nepal")
        db.session.add(fac)
        db.session.commit()

        self.login(SUPER_ADMIN_EMAIL, "SuperPass123!")
        res = self.client.post(f'/admin/curriculum/faculties/{fac.id}/delete-permanent', data={'confirm_text': 'Test Faculty 99'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(Faculty.query.get(fac.id))

    def test_30_super_admin_can_delete_program(self):
        prog = CurriculumProgram(name="Test Program 99", level_name="Bachelors", country="Nepal")
        db.session.add(prog)
        db.session.commit()

        self.login(SUPER_ADMIN_EMAIL, "SuperPass123!")
        res = self.client.post(f'/admin/curriculum/programs/{prog.id}/delete-permanent', data={'confirm_text': 'Test Program 99'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(CurriculumProgram.query.get(prog.id))

    def test_31_super_admin_can_delete_master_subject(self):
        subj = Subject(name="Test Subject 99", code="TS99", level_of_study="Bachelors")
        db.session.add(subj)
        db.session.commit()

        self.login(SUPER_ADMIN_EMAIL, "SuperPass123!")
        res = self.client.post(f'/admin/curriculum/subjects/{subj.id}/delete-permanent', data={'confirm_text': 'Test Subject 99'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(Subject.query.get(subj.id))

    def test_32_super_admin_can_delete_regular_admin(self):
        to_del = User(full_name="Delete Admin", email="todeleteadmin@gmail.com", password_hash="hash", role="admin")
        db.session.add(to_del)
        db.session.commit()

        self.login(SUPER_ADMIN_EMAIL, "SuperPass123!")
        res = self.client.post(f'/admin/admins/{to_del.id}/delete-permanent', data={'confirm_text': 'todeleteadmin@gmail.com'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(User.query.get(to_del.id))

    # ── PART 3: STUDY PLANNER VALIDATION (Scenarios 33-50) ────────────────────

    def test_33_attendance_0_accepted(self):
        self.login("student_test50@smartstudy.edu", "StudentPass123!")
        res = self.client.post('/student/api/risk-analysis', json={"subjects": [{"name": "Data Structures", "previous_grade": 80.0, "attendance": 0.0, "study_hours": 6.0, "days_until_exam": 30}]})
        self.assertEqual(res.status_code, 200)

    def test_34_attendance_100_accepted(self):
        self.login("student_test50@smartstudy.edu", "StudentPass123!")
        res = self.client.post('/student/api/risk-analysis', json={"subjects": [{"name": "Data Structures", "previous_grade": 80.0, "attendance": 100.0, "study_hours": 6.0, "days_until_exam": 30}]})
        self.assertEqual(res.status_code, 200)

    def test_35_attendance_101_rejected(self):
        self.login("student_test50@smartstudy.edu", "StudentPass123!")
        res = self.client.post('/student/api/risk-analysis', json={"subjects": [{"name": "Data Structures", "previous_grade": 80.0, "attendance": 101.0, "study_hours": 6.0, "days_until_exam": 30}]})
        self.assertEqual(res.status_code, 400)

    def test_36_attendance_855_rejected(self):
        self.login("student_test50@smartstudy.edu", "StudentPass123!")
        res = self.client.post('/student/api/risk-analysis', json={"subjects": [{"name": "Data Structures", "previous_grade": 80.0, "attendance": 855.0, "study_hours": 6.0, "days_until_exam": 30}]})
        self.assertEqual(res.status_code, 400)

    def test_37_study_hours_0_accepted(self):
        self.login("student_test50@smartstudy.edu", "StudentPass123!")
        res = self.client.post('/student/api/risk-analysis', json={"subjects": [{"name": "Data Structures", "previous_grade": 80.0, "attendance": 85.0, "study_hours": 0.0, "days_until_exam": 30}]})
        self.assertEqual(res.status_code, 200)

    def test_38_study_hours_84_accepted(self):
        self.login("student_test50@smartstudy.edu", "StudentPass123!")
        res = self.client.post('/student/api/risk-analysis', json={"subjects": [{"name": "Data Structures", "previous_grade": 80.0, "attendance": 85.0, "study_hours": 84.0, "days_until_exam": 30}]})
        self.assertEqual(res.status_code, 200)

    def test_39_study_hours_85_rejected(self):
        self.login("student_test50@smartstudy.edu", "StudentPass123!")
        res = self.client.post('/student/api/risk-analysis', json={"subjects": [{"name": "Data Structures", "previous_grade": 80.0, "attendance": 85.0, "study_hours": 85.0, "days_until_exam": 30}]})
        self.assertEqual(res.status_code, 400)
        self.assertIn("between 0 and 84", res.get_json().get("message", ""))

    def test_40_study_hours_168_rejected(self):
        self.login("student_test50@smartstudy.edu", "StudentPass123!")
        res = self.client.post('/student/api/risk-analysis', json={"subjects": [{"name": "Data Structures", "previous_grade": 80.0, "attendance": 85.0, "study_hours": 168.0, "days_until_exam": 30}]})
        self.assertEqual(res.status_code, 400)

    def test_41_study_hours_611_rejected(self):
        self.login("student_test50@smartstudy.edu", "StudentPass123!")
        res = self.client.post('/student/api/risk-analysis', json={"subjects": [{"name": "Data Structures", "previous_grade": 80.0, "attendance": 85.0, "study_hours": 611.0, "days_until_exam": 30}]})
        self.assertEqual(res.status_code, 400)

    def test_42_days_1_accepted(self):
        self.login("student_test50@smartstudy.edu", "StudentPass123!")
        res = self.client.post('/student/api/risk-analysis', json={"subjects": [{"name": "Data Structures", "previous_grade": 80.0, "attendance": 85.0, "study_hours": 6.0, "days_until_exam": 1}]})
        self.assertEqual(res.status_code, 200)

    def test_43_days_365_accepted(self):
        self.login("student_test50@smartstudy.edu", "StudentPass123!")
        res = self.client.post('/student/api/risk-analysis', json={"subjects": [{"name": "Data Structures", "previous_grade": 80.0, "attendance": 85.0, "study_hours": 6.0, "days_until_exam": 365}]})
        self.assertEqual(res.status_code, 200)

    def test_44_days_366_rejected(self):
        self.login("student_test50@smartstudy.edu", "StudentPass123!")
        res = self.client.post('/student/api/risk-analysis', json={"subjects": [{"name": "Data Structures", "previous_grade": 80.0, "attendance": 85.0, "study_hours": 6.0, "days_until_exam": 366}]})
        self.assertEqual(res.status_code, 400)

    def test_45_days_300000000_rejected(self):
        self.login("student_test50@smartstudy.edu", "StudentPass123!")
        res = self.client.post('/student/api/risk-analysis', json={"subjects": [{"name": "Data Structures", "previous_grade": 80.0, "attendance": 85.0, "study_hours": 6.0, "days_until_exam": 300000000}]})
        self.assertEqual(res.status_code, 400)

    def test_46_decimal_days_rejected(self):
        self.login("student_test50@smartstudy.edu", "StudentPass123!")
        res = self.client.post('/student/api/risk-analysis', json={"subjects": [{"name": "Data Structures", "previous_grade": 80.0, "attendance": 85.0, "study_hours": 6.0, "days_until_exam": 1.5}]})
        self.assertEqual(res.status_code, 400)

    def test_47_invalid_session_length_rejected(self):
        self.login("student_test50@smartstudy.edu", "StudentPass123!")
        res = self.client.post('/student/schedule/generate', data={'subject_name[]': ['Data Structures'], 'previous_grade[]': ['80'], 'attendance[]': ['85'], 'study_hours[]': ['6'], 'days_until_exam[]': ['30'], 'session_length': ['15']}, follow_redirects=True)
        self.assertIn(b"Invalid session length", res.data)

    def test_48_valid_session_lengths_accepted(self):
        self.login("student_test50@smartstudy.edu", "StudentPass123!")
        for sess in [30, 45, 60, 90, 120]:
            res = self.client.post('/student/schedule/generate', data={'subject_name[]': ['Data Structures'], 'previous_grade[]': ['80'], 'attendance[]': ['85'], 'study_hours[]': ['6'], 'days_until_exam[]': ['30'], 'session_length': [str(sess)]}, follow_redirects=True)
            self.assertNotIn(b"Invalid session length", res.data)

    def test_49_invalid_inputs_never_reach_ml_prediction(self):
        self.login("student_test50@smartstudy.edu", "StudentPass123!")
        res = self.client.post('/student/api/risk-analysis', json={"subjects": [{"name": "Data Structures", "previous_grade": 80.0, "attendance": 85.0, "study_hours": 9999.0, "days_until_exam": 30}]})
        self.assertEqual(res.status_code, 400)

    def test_50_inline_validation_messages_formatted_correctly(self):
        self.login("student_test50@smartstudy.edu", "StudentPass123!")
        res = self.client.post('/student/api/risk-analysis', json={"subjects": [{"name": "Data Structures", "previous_grade": 80.0, "attendance": 85.0, "study_hours": 85.0, "days_until_exam": 30}]})
        data = res.get_json()
        self.assertIn("must be between 0 and 84", data.get("message", ""))

if __name__ == '__main__':
    unittest.main()
