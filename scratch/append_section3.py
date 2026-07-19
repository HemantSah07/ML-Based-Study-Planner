section3_code = '''

# ── SECTION 3: STUDENT MANAGEMENT ─────────────────────────────────────────────

from math import ceil

@admin_bp.route("/students")
def students():
    from app.models import StudyPlan, StudentAssessment
    page = request.args.get("page", 1, type=int)
    per_page = 25
    search_q = request.args.get("q", "").strip()
    selected_level = request.args.get("level", "").strip()
    selected_status = request.args.get("status", "").strip()

    from app.models import EducationLevel
    levels = EducationLevel.query.filter_by(is_active=True).order_by(EducationLevel.sort_order).all()

    query = User.query.filter_by(role="student")
    if search_q:
        from sqlalchemy import or_
        query = query.filter(or_(
            User.full_name.ilike(f"%{search_q}%"),
            User.email.ilike(f"%{search_q}%")
        ))
    if selected_status == "active":
        query = query.filter_by(is_active=True)
    elif selected_status == "inactive":
        query = query.filter_by(is_active=False)

    total = query.count()
    pages = ceil(total / per_page) if total else 1
    users = query.order_by(User.date_registered.desc()).offset((page - 1) * per_page).limit(per_page).all()

    rows = []
    for u in users:
        prof = u.profile
        profile_complete = bool(prof and prof.country and prof.study_level)
        assessed = bool(prof and prof.has_completed_assessment)
        has_subjects = StudentSubject.query.filter_by(user_id=u.id).count() > 0
        has_planner = StudyPlan.query.filter_by(student_id=u.id).count() > 0
        rows.append({
            "user": u, "profile": prof,
            "profile_complete": profile_complete,
            "assessed": assessed, "has_subjects": has_subjects, "has_planner": has_planner,
        })

    stats = {
        "total": User.query.filter_by(role="student").count(),
        "complete_profile": StudentProfile.query.filter(StudentProfile.country != None, StudentProfile.study_level != None).count(),
        "assessed": StudentProfile.query.filter_by(has_completed_assessment=True).count(),
        "active": User.query.filter_by(role="student", is_active=True).count(),
    }

    return render_template(
        "admin/students/list.html",
        students=rows, page=page, pages=pages,
        stats=stats, levels=levels,
        search_q=search_q, selected_level=selected_level, selected_status=selected_status,
    )


@admin_bp.route("/students/<int:student_id>")
def student_detail(student_id):
    from app.models import Prediction, StudentAssessment, Subject as SubjectModel, StudyPlan
    student = User.query.get_or_404(student_id)
    profile = student.profile
    subjects = StudentSubject.query.filter_by(user_id=student_id).all()
    latest_prediction = Prediction.query.filter_by(user_id=student_id).order_by(Prediction.date.desc()).first()
    assessments = StudentAssessment.query.filter_by(student_id=student_id).order_by(StudentAssessment.completed_at.desc()).limit(10).all()
    # attach subject name
    for a in assessments:
        a.subject = SubjectModel.query.get(a.subject_id) if a.subject_id else None
    study_plan = StudyPlan.query.filter_by(student_id=student_id).order_by(StudyPlan.generated_at.desc()).first()
    return render_template(
        "admin/students/detail.html",
        student=student, profile=profile, subjects=subjects,
        latest_prediction=latest_prediction,
        assessments=assessments,
        study_plan=study_plan,
    )


@admin_bp.route("/students/<int:student_id>/impersonate", methods=["POST"])
def impersonate(student_id):
    student = User.query.get_or_404(student_id)
    if student.role != "student":
        flash("You can only impersonate student accounts.", "warning")
        return redirect(url_for("admin.student_detail", student_id=student_id))
    from flask import session as flask_session
    flask_session["impersonating_student_id"] = student_id
    log_admin_action("impersonate_student", "User", student_id, f"Started impersonating student '{student.email}'")
    flash(f"Now viewing as student: {student.full_name or student.email}", "info")
    from flask import redirect, url_for
    return redirect("/student/dashboard")


@admin_bp.route("/impersonate/exit")
def exit_impersonate():
    from flask import session as flask_session
    impersonate_id = flask_session.pop("impersonating_student_id", None)
    if impersonate_id:
        student = User.query.get(impersonate_id)
        log_admin_action("exit_impersonation", "User", impersonate_id, f"Exited impersonation of student ID {impersonate_id}")
        flash(f"Exited impersonation mode.", "success")
        return redirect(url_for("admin.student_detail", student_id=impersonate_id))
    return redirect(url_for("admin.students"))


@admin_bp.route("/students/<int:student_id>/run-ml", methods=["POST"])
def student_run_ml(student_id):
    student = User.query.get_or_404(student_id)
    try:
        from app.routes.student import _run_prediction_for_user
        _run_prediction_for_user(student.id)
        log_admin_action("run_ml_prediction", "User", student_id, f"Manually triggered ML prediction for student {student.email}")
        flash(f"ML prediction re-run for {student.full_name or student.email} — check their profile.", "success")
    except Exception as e:
        # Fallback: trigger via context
        try:
            from app.context.learning_context import get_learning_context
            ctx = get_learning_context(student_id, force_refresh=True)
            # Call the predict route in service mode
            from app.services.ml_service import run_prediction
            result = run_prediction(student_id)
            if result:
                log_admin_action("run_ml_prediction", "User", student_id, f"ML re-run via service for {student.email}")
                flash(f"ML prediction updated for {student.full_name or student.email}.", "success")
            else:
                flash(f"ML prediction returned no result — may need more study data.", "warning")
        except Exception as e2:
            flash(f"Could not run ML prediction: {e2}", "danger")
    return redirect(url_for("admin.student_detail", student_id=student_id))


@admin_bp.route("/students/<int:student_id>/reset-assessment", methods=["POST"])
def student_reset_assessment(student_id):
    from app.models import StudentProfile
    profile = StudentProfile.query.filter_by(user_id=student_id).first()
    if profile:
        profile.has_completed_assessment = False
        db.session.commit()
    # Clear any session state for that student
    log_admin_action("reset_assessment", "User", student_id, f"Reset assessment session for student ID {student_id}")
    flash("Assessment session reset. Student can now start fresh.", "success")
    return redirect(url_for("admin.student_detail", student_id=student_id))


@admin_bp.route("/students/<int:student_id>/toggle-active", methods=["POST"])
def student_toggle_active(student_id):
    student = User.query.get_or_404(student_id)
    student.is_active = not student.is_active
    db.session.commit()
    action_str = "activated" if student.is_active else "suspended"
    log_admin_action(f"{action_str}_student_account", "User", student_id, f"Account {action_str} for student {student.email}")
    flash(f"Account {action_str} for {student.full_name or student.email}.", "success")
    return redirect(url_for("admin.student_detail", student_id=student_id))
'''

with open('app/routes/admin.py', 'a', encoding='utf-8') as f:
    f.write(section3_code)

print("SUCCESS: Section 3 routes appended to admin.py")
