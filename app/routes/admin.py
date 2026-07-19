from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, session
from flask_login import login_required, current_user
from app import db
from app.models import (
    User, Prediction, StudyLog, StudentProfile, StudentSubject,
    EducationLevel, University, Faculty, CurriculumProgram, Subject, AdminActivityLog
)
from datetime import datetime, timedelta
import json

admin_bp = Blueprint("admin", __name__)

@admin_bp.before_request
@login_required
def require_admin():
    if current_user.role != 'admin':
        return redirect(url_for('student.dashboard'))

def log_admin_action(action, entity_type=None, entity_id=None, detail=None):
    try:
        log = AdminActivityLog(
            admin_user_id=current_user.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            detail=detail
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error logging admin action: {e}")

@admin_bp.route("/dashboard")
def dashboard():
    total_students = User.query.filter_by(role='student').count()
    total_predictions = Prediction.query.count()
    total_study_hours = sum(log.duration_hours for log in StudyLog.query.all())

    chart_labels = []
    chart_data = []
    for i in range(3, -1, -1):
        week_start = datetime.utcnow() - timedelta(days=7 * (i + 1))
        week_end = datetime.utcnow() - timedelta(days=7 * i)
        count = Prediction.query.filter(
            Prediction.date >= week_start,
            Prediction.date < week_end,
        ).count()
        chart_labels.append(f"Week {4 - i}")
        chart_data.append(count)
    
    return render_template("admin/dashboard.html", 
                           total_students=total_students,
                           total_predictions=total_predictions,
                           total_study_hours=total_study_hours,
                           chart_labels=chart_labels,
                           chart_data=chart_data)


# ── SECTION 1: CURRICULUM LEVELS CRUD ─────────────────────────────────────────

@admin_bp.route("/curriculum/levels")
def curriculum_levels():
    levels = EducationLevel.query.order_by(EducationLevel.sort_order.asc()).all()
    # Calculate student usage counts
    usage_counts = {}
    for lvl in levels:
        usage_counts[lvl.name] = StudentProfile.query.filter_by(study_level=lvl.name).count()
    return render_template("admin/curriculum/levels.html", levels=levels, usage_counts=usage_counts)

@admin_bp.route("/curriculum/levels/add", methods=["POST"])
def curriculum_levels_add():
    name = request.form.get("name", "").strip()
    country = request.form.get("country", "").strip()
    sort_order = int(request.form.get("sort_order", 0))
    if name and country:
        level = EducationLevel(name=name, country=country, sort_order=sort_order, is_active=True)
        db.session.add(level)
        db.session.commit()
        log_admin_action("add_education_level", "EducationLevel", level.id, f"Added level '{name}' for country '{country}'")
        flash(f"Education level '{name}' added successfully!", "success")
    else:
        flash("Name and Country are required fields.", "danger")
    return redirect(url_for("admin.curriculum_levels"))

@admin_bp.route("/curriculum/levels/<int:level_id>/edit", methods=["POST"])
def curriculum_levels_edit(level_id):
    level = EducationLevel.query.get_or_404(level_id)
    old_name = level.name
    level.name = request.form.get("name", "").strip()
    level.country = request.form.get("country", "").strip()
    level.sort_order = int(request.form.get("sort_order", 0))
    db.session.commit()
    log_admin_action("edit_education_level", "EducationLevel", level.id, f"Edited level '{old_name}' -> '{level.name}'")
    flash(f"Education level '{level.name}' updated successfully!", "success")
    return redirect(url_for("admin.curriculum_levels"))

@admin_bp.route("/curriculum/levels/<int:level_id>/toggle", methods=["POST"])
def curriculum_levels_toggle(level_id):
    level = EducationLevel.query.get_or_404(level_id)
    level.is_active = not level.is_active
    db.session.commit()
    action_str = "activated" if level.is_active else "deactivated"
    log_admin_action(f"{action_str}_education_level", "EducationLevel", level.id, f"Set is_active={level.is_active} for '{level.name}'")
    flash(f"Education level '{level.name}' {action_str} successfully!", "success")
    return redirect(url_for("admin.curriculum_levels"))


# ── SECTION 1: UNIVERSITIES CRUD ──────────────────────────────────────────────

@admin_bp.route("/curriculum/universities")
def curriculum_universities():
    universities = University.query.order_by(University.sort_order.asc()).all()
    usage_counts = {}
    for uni in universities:
        # Check profiles starting with uni name (e.g. "Tribhuvan University (TU)")
        usage_counts[uni.name] = StudentProfile.query.filter(StudentProfile.university.like(f"{uni.name}%")).count()
    return render_template("admin/curriculum/universities.html", universities=universities, usage_counts=usage_counts)

@admin_bp.route("/curriculum/universities/add", methods=["POST"])
def curriculum_universities_add():
    name = request.form.get("name", "").strip()
    abbr = request.form.get("abbreviation", "").strip() or None
    country = request.form.get("country", "").strip()
    sort_order = int(request.form.get("sort_order", 0))
    if name and country:
        uni = University(name=name, abbreviation=abbr, country=country, sort_order=sort_order, is_active=True)
        db.session.add(uni)
        db.session.commit()
        log_admin_action("add_university", "University", uni.id, f"Added university '{name}' ({abbr or 'no abbr'})")
        flash(f"University '{name}' added successfully!", "success")
    else:
        flash("Name and Country are required.", "danger")
    return redirect(url_for("admin.curriculum_universities"))

@admin_bp.route("/curriculum/universities/<int:uni_id>/edit", methods=["POST"])
def curriculum_universities_edit(uni_id):
    uni = University.query.get_or_404(uni_id)
    old_name = uni.name
    uni.name = request.form.get("name", "").strip()
    uni.abbreviation = request.form.get("abbreviation", "").strip() or None
    uni.country = request.form.get("country", "").strip()
    uni.sort_order = int(request.form.get("sort_order", 0))
    db.session.commit()
    log_admin_action("edit_university", "University", uni.id, f"Edited university '{old_name}' -> '{uni.name}'")
    flash(f"University '{uni.name}' updated successfully!", "success")
    return redirect(url_for("admin.curriculum_universities"))

@admin_bp.route("/curriculum/universities/<int:uni_id>/toggle", methods=["POST"])
def curriculum_universities_toggle(uni_id):
    uni = University.query.get_or_404(uni_id)
    uni.is_active = not uni.is_active
    db.session.commit()
    action_str = "activated" if uni.is_active else "deactivated"
    log_admin_action(f"{action_str}_university", "University", uni.id, f"Set is_active={uni.is_active} for '{uni.name}'")
    flash(f"University '{uni.name}' {action_str} successfully!", "success")
    return redirect(url_for("admin.curriculum_universities"))


# ── SECTION 1: FACULTIES CRUD ─────────────────────────────────────────────────

@admin_bp.route("/curriculum/faculties")
def curriculum_faculties():
    faculties = Faculty.query.order_by(Faculty.sort_order.asc()).all()
    usage_counts = {}
    for fac in faculties:
        usage_counts[fac.name] = StudentProfile.query.filter_by(program=fac.name).count()
    return render_template("admin/curriculum/faculties.html", faculties=faculties, usage_counts=usage_counts)

@admin_bp.route("/curriculum/faculties/add", methods=["POST"])
def curriculum_faculties_add():
    name = request.form.get("name", "").strip()
    lvl = request.form.get("level_name", "").strip() or None
    sort_order = int(request.form.get("sort_order", 0))
    if name:
        fac = Faculty(name=name, level_name=lvl, country="Nepal", sort_order=sort_order, is_active=True)
        db.session.add(fac)
        db.session.commit()
        log_admin_action("add_faculty", "Faculty", fac.id, f"Added faculty '{name}' for level '{lvl or 'All'}'")
        flash(f"Faculty '{name}' added successfully!", "success")
    else:
        flash("Name is required.", "danger")
    return redirect(url_for("admin.curriculum_faculties"))

@admin_bp.route("/curriculum/faculties/<int:fac_id>/edit", methods=["POST"])
def curriculum_faculties_edit(fac_id):
    fac = Faculty.query.get_or_404(fac_id)
    old_name = fac.name
    fac.name = request.form.get("name", "").strip()
    fac.level_name = request.form.get("level_name", "").strip() or None
    fac.sort_order = int(request.form.get("sort_order", 0))
    db.session.commit()
    log_admin_action("edit_faculty", "Faculty", fac.id, f"Edited faculty '{old_name}' -> '{fac.name}'")
    flash(f"Faculty '{fac.name}' updated successfully!", "success")
    return redirect(url_for("admin.curriculum_faculties"))

@admin_bp.route("/curriculum/faculties/<int:fac_id>/toggle", methods=["POST"])
def curriculum_faculties_toggle(fac_id):
    fac = Faculty.query.get_or_404(fac_id)
    fac.is_active = not fac.is_active
    db.session.commit()
    action_str = "activated" if fac.is_active else "deactivated"
    log_admin_action(f"{action_str}_faculty", "Faculty", fac.id, f"Set is_active={fac.is_active} for '{fac.name}'")
    flash(f"Faculty '{fac.name}' {action_str} successfully!", "success")
    return redirect(url_for("admin.curriculum_faculties"))


# ── SECTION 1: PROGRAMS CRUD ──────────────────────────────────────────────────

@admin_bp.route("/curriculum/programs")
def curriculum_programs():
    programs = CurriculumProgram.query.order_by(CurriculumProgram.sort_order.asc()).all()
    usage_counts = {}
    for prog in programs:
        usage_counts[prog.name] = StudentProfile.query.filter_by(program=prog.name).count()
    return render_template("admin/curriculum/programs.html", programs=programs, usage_counts=usage_counts)

@admin_bp.route("/curriculum/programs/add", methods=["POST"])
def curriculum_programs_add():
    name = request.form.get("name", "").strip()
    lvl = request.form.get("level_name", "").strip()
    has_duration = bool(request.form.get("has_duration"))
    sort_order = int(request.form.get("sort_order", 0))
    if name and lvl:
        dur_json = None
        if has_duration:
            # Seed default duration choices for Bachelors duration-variable programs
            dur_json = json.dumps([
                {"value": "3 Years", "label": "3 Years (International-affiliated, e.g. APU/LBEF)"},
                {"value": "4 Years", "label": "4 Years (TU-affiliated BSc CSIT)"}
            ])
        prog = CurriculumProgram(
            name=name, level_name=lvl, country="Nepal",
            has_duration=has_duration, duration_options_json=dur_json,
            sort_order=sort_order, is_active=True
        )
        db.session.add(prog)
        db.session.commit()
        log_admin_action("add_program", "CurriculumProgram", prog.id, f"Added program '{name}' under '{lvl}'")
        flash(f"Program '{name}' added successfully!", "success")
    else:
        flash("Name and Level Name are required.", "danger")
    return redirect(url_for("admin.curriculum_programs"))

@admin_bp.route("/curriculum/programs/<int:prog_id>/edit", methods=["POST"])
def curriculum_programs_edit(prog_id):
    prog = CurriculumProgram.query.get_or_404(prog_id)
    old_name = prog.name
    prog.name = request.form.get("name", "").strip()
    prog.level_name = request.form.get("level_name", "").strip()
    prog.has_duration = bool(request.form.get("has_duration"))
    prog.sort_order = int(request.form.get("sort_order", 0))
    if prog.has_duration and not prog.duration_options_json:
        prog.duration_options_json = json.dumps([
            {"value": "3 Years", "label": "3 Years (International-affiliated, e.g. APU/LBEF)"},
            {"value": "4 Years", "label": "4 Years (TU-affiliated BSc CSIT)"}
        ])
    elif not prog.has_duration:
        prog.duration_options_json = None
    db.session.commit()
    log_admin_action("edit_program", "CurriculumProgram", prog.id, f"Edited program '{old_name}' -> '{prog.name}'")
    flash(f"Program '{prog.name}' updated successfully!", "success")
    return redirect(url_for("admin.curriculum_programs"))

@admin_bp.route("/curriculum/programs/<int:prog_id>/toggle", methods=["POST"])
def curriculum_programs_toggle(prog_id):
    prog = CurriculumProgram.query.get_or_404(prog_id)
    prog.is_active = not prog.is_active
    db.session.commit()
    action_str = "activated" if prog.is_active else "deactivated"
    log_admin_action(f"{action_str}_program", "CurriculumProgram", prog.id, f"Set is_active={prog.is_active} for '{prog.name}'")
    flash(f"Program '{prog.name}' {action_str} successfully!", "success")
    return redirect(url_for("admin.curriculum_programs"))


# ── SECTION 1: SUBJECTS CRUD ──────────────────────────────────────────────────

@admin_bp.route("/curriculum/subjects")
def curriculum_subjects():
    selected_level = request.args.get("level", "").strip()
    levels = EducationLevel.query.filter_by(is_active=True).order_by(EducationLevel.sort_order.asc()).all()
    
    query = Subject.query
    if selected_level:
        query = query.filter_by(level_of_study=selected_level)
    subjects = query.order_by(Subject.level_of_study.asc(), Subject.name.asc()).all()
    
    usage_counts = {}
    for s in subjects:
        usage_counts[s.id] = StudentSubject.query.filter_by(subject_id=s.id).count()
        
    return render_template(
        "admin/curriculum/subjects.html",
        subjects=subjects,
        levels=levels,
        selected_level=selected_level,
        usage_counts=usage_counts
    )

@admin_bp.route("/curriculum/subjects/add", methods=["POST"])
def curriculum_subjects_add():
    lvl_filter = request.form.get("level_filter", "").strip()
    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip() or None
    lvl = request.form.get("level_of_study", "").strip()
    program = request.form.get("program", "").strip() or None
    semester = request.form.get("semester", "").strip() or None
    credit_hours = int(request.form.get("credit_hours", 3))
    difficulty = int(request.form.get("difficulty_level", 3))
    
    if name and lvl:
        subj = Subject(
            name=name, code=code, level_of_study=lvl,
            program=program, semester=semester,
            credit_hours=credit_hours, difficulty_level=difficulty,
            country="Nepal", curriculum="NEB/CTEVT" if lvl in ("Class 11", "Class 12") else "National",
            is_active=True
        )
        db.session.add(subj)
        db.session.commit()
        log_admin_action("add_subject", "Subject", subj.id, f"Added subject '{name}' ({code or 'no code'}) under '{lvl}'")
        flash(f"Subject '{name}' added successfully!", "success")
    else:
        flash("Subject Name and Level are required.", "danger")
        
    return redirect(url_for("admin.curriculum_subjects", level=lvl_filter))

@admin_bp.route("/curriculum/subjects/<int:subject_id>/edit", methods=["POST"])
def curriculum_subjects_edit(subject_id):
    subj = Subject.query.get_or_404(subject_id)
    lvl_filter = request.form.get("level_filter", "").strip()
    old_name = subj.name
    
    subj.name = request.form.get("name", "").strip()
    subj.code = request.form.get("code", "").strip() or None
    subj.level_of_study = request.form.get("level_of_study", "").strip()
    subj.program = request.form.get("program", "").strip() or None
    subj.semester = request.form.get("semester", "").strip() or None
    subj.credit_hours = int(request.form.get("credit_hours", 3))
    subj.difficulty_level = int(request.form.get("difficulty_level", 3))
    
    db.session.commit()
    log_admin_action("edit_subject", "Subject", subj.id, f"Edited subject '{old_name}' -> '{subj.name}'")
    flash(f"Subject '{subj.name}' updated successfully!", "success")
    return redirect(url_for("admin.curriculum_subjects", level=lvl_filter))

@admin_bp.route("/curriculum/subjects/<int:subject_id>/toggle", methods=["POST"])
def curriculum_subjects_toggle(subject_id):
    subj = Subject.query.get_or_404(subject_id)
    lvl_filter = request.form.get("level_filter", "").strip()
    subj.is_active = not subj.is_active
    db.session.commit()
    action_str = "activated" if subj.is_active else "deactivated"
    log_admin_action(f"{action_str}_subject", "Subject", subj.id, f"Set is_active={subj.is_active} for '{subj.name}'")
    flash(f"Subject '{subj.name}' {action_str} successfully!", "success")
    return redirect(url_for("admin.curriculum_subjects", level=lvl_filter))


# ── SECTION 6: ACTIVITY LOG VIEW ──────────────────────────────────────────────

@admin_bp.route("/activity-log")
def activity_log():
    page = request.args.get("page", 1, type=int)
    per_page = 20
    
    pagination = AdminActivityLog.query.order_by(AdminActivityLog.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template(
        "admin/activity_log.html",
        logs=pagination.items,
        page=page,
        pages=pagination.pages,
        total=pagination.total
    )


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
        from app.routes.student import (
            get_profile_subjects, get_subject_performance_snapshot,
            get_subject_features, load_ml_model,
        )
        import numpy as np
        profile = StudentProfile.query.filter_by(user_id=student_id).first()
        student_subjects = get_profile_subjects(profile)
        if not student_subjects:
            flash("Student has no subjects configured. Cannot run ML.", "warning")
            return redirect(url_for("admin.student_detail", student_id=student_id))

        raw_gpa = float(profile.cumulative_gpa or profile.prior_academic_score or 0.0)
        profile_grade = raw_gpa * 25 if raw_gpa <= 4.0 else raw_gpa
        attendance = float(profile.attendance_pct or 85.0)
        target_weekly_hours = float(profile.target_weekly_hours or 14.0)
        per_subject_weekly_hours = max(1.0, target_weekly_hours / max(1, len(student_subjects)))
        model = load_ml_model("random_forest")
        scaler = load_ml_model("scaler")

        prediction_rank = {"low": 0, "medium": 1, "high": 2}
        overall_risk = "low"

        for subject in student_subjects:
            snapshot = get_subject_performance_snapshot(student_id, subject.id)
            if snapshot["source"] == "missing" or snapshot["score"] is None:
                continue
            performance_score = snapshot["score"]
            difficulty = float(subject.difficulty_level or 3.0)
            features = get_subject_features(
                student_id, subject.name, performance_score,
                attendance, per_subject_weekly_hours, difficulty, 30, None,
            )
            if model and scaler:
                f_scaled = scaler.transform(np.array([features]))
                if hasattr(model, "predict_proba"):
                    probs = model.predict_proba(f_scaled)[0]
                    risk_pred = int(np.argmax(probs))
                else:
                    risk_pred = min(2, max(0, int(model.predict(f_scaled)[0])))
            else:
                risk_pred = 1
            risk_lvl = ["low", "medium", "high"][risk_pred]
            if prediction_rank.get(risk_lvl, 0) > prediction_rank.get(overall_risk, 0):
                overall_risk = risk_lvl

        # Store/update the overall prediction
        existing = Prediction.query.filter_by(user_id=student_id).order_by(Prediction.date.desc()).first()
        if existing:
            existing.predicted_risk_level = overall_risk
            existing.date = datetime.utcnow()
        else:
            new_pred = Prediction(user_id=student_id, predicted_risk_level=overall_risk, date=datetime.utcnow())
            db.session.add(new_pred)
        db.session.commit()

        log_admin_action("run_ml_prediction", "User", student_id, f"ML re-run: risk={overall_risk} for {student.email}")
        flash(f"ML prediction updated for {student.full_name or student.email} — Risk: {overall_risk.upper()}", "success")
    except Exception as e:
        flash(f"Could not run ML prediction: {e}", "danger")
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


# ── SECTION 4 STUB: HEALTH ────────────────────────────────────────────────────
@admin_bp.route("/health")
def health():
    from flask import current_app
    checks = {
        "db": _check_db(),
        "gemini": _check_gemini_api(),
        "ml": _check_ml_model(),
    }
    disk = _get_disk_info()
    python_info = _get_python_info()
    model_config = _get_model_config()
    overall = "ok"
    for v in checks.values():
        if v.get("status") == "error":
            overall = "degraded"
            break
        elif v.get("status") in ("missing", "unconfigured") and overall != "degraded":
            overall = "warning"

    # Today's API usage (Section 4 requirement)
    api_usage = _get_daily_api_usage()

    # Count subjects with zero assessment questions
    from app.models import AssessmentQuestion
    from app.models import Subject as _Subj
    subjects_zero_q = 0
    try:
        all_subjects = _Subj.query.filter_by(is_active=True).all()
        for s in all_subjects:
            if AssessmentQuestion.query.filter_by(subject_id=s.id).count() == 0:
                subjects_zero_q += 1
    except Exception:
        subjects_zero_q = 0

    return render_template(
        "admin/health.html",
        checks=checks, disk=disk, python_info=python_info,
        model_config=model_config, overall=overall,
        api_usage=api_usage, subjects_zero_q=subjects_zero_q,
    )



# ── SECTION 2 STUB: CONTENT ──────────────────────────────────────────────────
@admin_bp.route("/content")
def content_subjects():
    """Redirect main /content to the stats overview."""
    return redirect(url_for("admin.content_stats"))


# ── SECTION 5: COHORT ANALYTICS ──────────────────────────────────────────────
@admin_bp.route("/analytics")
def analytics():
    from app.models import StudentProfile, Prediction, StudyLog, StudentAssessment, EducationLevel
    from sqlalchemy import func
    
    # Get all active cohorts (Education Levels)
    levels = [l.name for l in EducationLevel.query.filter_by(is_active=True).order_by(EducationLevel.sort_order).all()]
    
    # Fallback to distinct study_levels if EducationLevel is empty
    if not levels:
        levels = [r[0] for r in db.session.query(StudentProfile.study_level).distinct().all() if r[0]]
        
    cohort_data = {}
    for lvl in levels:
        # Get student profiles in this cohort
        profiles = StudentProfile.query.filter_by(study_level=lvl).all()
        student_ids = [p.user_id for p in profiles]
        
        if not student_ids:
            cohort_data[lvl] = {
                "student_count": 0,
                "high_risk": 0, "medium_risk": 0, "low_risk": 0, "unknown_risk": 0,
                "avg_gpa": 0.0, "avg_study_hours": 0.0, "avg_assessment": 0.0
            }
            continue
            
        # Risk distribution (using latest prediction for each student)
        high = 0
        medium = 0
        low = 0
        unknown = 0
        for sid in student_ids:
            pred = Prediction.query.filter_by(user_id=sid).order_by(Prediction.date.desc()).first()
            if pred:
                risk = (pred.predicted_risk_level or "").lower()
                if "high" in risk: high += 1
                elif "medium" in risk: medium += 1
                elif "low" in risk: low += 1
                else: unknown += 1
            else:
                unknown += 1
                
        # Metrics
        gpas = [p.cumulative_gpa for p in profiles if p.cumulative_gpa is not None]
        avg_gpa = round(sum(gpas) / len(gpas), 2) if gpas else 0.0
        
        # Study Hours
        total_hours = db.session.query(func.sum(StudyLog.duration_hours)).filter(StudyLog.user_id.in_(student_ids)).scalar() or 0.0
        avg_study_hours = round(total_hours / len(student_ids), 1)
        
        # Assessment
        scores = db.session.query(func.avg(StudentAssessment.weighted_score)).filter(StudentAssessment.student_id.in_(student_ids)).scalar() or 0.0
        avg_assessment = round(scores, 1)
        
        cohort_data[lvl] = {
            "student_count": len(student_ids),
            "high_risk": high,
            "medium_risk": medium,
            "low_risk": low,
            "unknown_risk": unknown,
            "avg_gpa": avg_gpa,
            "avg_study_hours": avg_study_hours,
            "avg_assessment": avg_assessment
        }
        
    # Overall summary metrics
    total_students = User.query.filter_by(role="student").count()
    overall_high = 0
    overall_medium = 0
    overall_low = 0
    # Query latest predictions for all students
    all_student_ids = [u.id for u in User.query.filter_by(role="student").all()]
    for sid in all_student_ids:
        pred = Prediction.query.filter_by(user_id=sid).order_by(Prediction.date.desc()).first()
        if pred:
            risk = (pred.predicted_risk_level or "").lower()
            if "high" in risk: overall_high += 1
            elif "medium" in risk: overall_medium += 1
            else: overall_low += 1
        else:
            overall_low += 1
            
    # Format a list of cohort dicts for easy rendering in jinja2
    cohort_list = []
    for lvl, metrics in cohort_data.items():
        metrics["level"] = lvl
        cohort_list.append(metrics)
        
    return render_template(
        "admin/analytics.html",
        cohorts=cohort_list,
        total_students=total_students,
        overall_high=overall_high,
        overall_medium=overall_medium,
        overall_low=overall_low
    )


# ── SECTION 7: RESTART-FREE LIVE CONFIGURATION ────────────────────────────────
@admin_bp.route("/config", methods=["GET", "POST"])
def config():
    from app.models import AppSetting
    from app.live_config import load_live_config
    
    if request.method == "POST":
        # Save all configs
        keys = [
            "GEMINI_API_KEY", "ANTHROPIC_API_KEY",
            "GEMINI_MODEL_MCQ", "GEMINI_MODEL_ASSISTANT_PRIMARY", "GEMINI_MODEL_ASSISTANT_FALLBACK",
            "GEMINI_DAILY_LIMIT_MCQ", "GEMINI_RPM_LIMIT_MCQ",
            "GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY", "GEMINI_DAILY_LIMIT_ASSISTANT_FALLBACK",
            "GEMINI_RPM_LIMIT_ASSISTANT_PRIMARY"
        ]
        for k in keys:
            val = request.form.get(k, "").strip()
            setting = AppSetting.query.get(k)
            if setting:
                setting.value = val
            else:
                setting = AppSetting(key=k, value=val)
                db.session.add(setting)
                
        # Billing switch
        billing = "True" if request.form.get("GEMINI_BILLING_ENABLED") else "False"
        setting = AppSetting.query.get("GEMINI_BILLING_ENABLED")
        if setting:
            setting.value = billing
        else:
            setting = AppSetting(key="GEMINI_BILLING_ENABLED", value=billing)
            db.session.add(setting)
            
        db.session.commit()
        
        # Instantly reload config cache
        load_live_config(current_app._get_current_object(), force=True)
        
        log_admin_action("update_config", "AppSetting", None, "Updated application settings and flushed config cache")
        flash("Configuration updated and cache reloaded successfully.", "success")
        return redirect(url_for("admin.config"))
        
    settings = {s.key: s.value for s in AppSetting.query.all()}
    return render_template("admin/config.html", settings=settings)


# ── SECTION 8: BULK OPERATIONS ────────────────────────────────────────────────
@admin_bp.route("/bulk", methods=["GET", "POST"])
def bulk():
    from app.models import Notification, EducationLevel, StudentProfile, Prediction
    
    levels = [l.name for l in EducationLevel.query.filter_by(is_active=True).order_by(EducationLevel.sort_order).all()]
    if not levels:
        levels = [r[0] for r in db.session.query(StudentProfile.study_level).distinct().all() if r[0]]
        
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "batch_ml":
            # Run predictions for all students
            students = User.query.filter_by(role="student").all()
            success_count = 0
            fail_count = 0
            
            from app.routes.student import (
                get_profile_subjects, get_subject_performance_snapshot,
                get_subject_features, load_ml_model,
            )
            import numpy as np
            
            model = load_ml_model("random_forest")
            scaler = load_ml_model("scaler")
            prediction_rank = {"low": 0, "medium": 1, "high": 2}
            
            for s in students:
                profile = StudentProfile.query.filter_by(user_id=s.id).first()
                if not profile:
                    fail_count += 1
                    continue
                    
                student_subjects = get_profile_subjects(profile)
                if not student_subjects:
                    fail_count += 1
                    continue
                    
                try:
                    raw_gpa = float(profile.cumulative_gpa or profile.prior_academic_score or 0.0)
                    attendance = float(profile.attendance_pct or 85.0)
                    target_weekly_hours = float(profile.target_weekly_hours or 14.0)
                    per_subject_weekly_hours = max(1.0, target_weekly_hours / max(1, len(student_subjects)))
                    
                    overall_risk = "low"
                    for subject in student_subjects:
                        snapshot = get_subject_performance_snapshot(s.id, subject.id)
                        if snapshot["source"] == "missing" or snapshot["score"] is None:
                            continue
                        performance_score = snapshot["score"]
                        difficulty = float(subject.difficulty_level or 3.0)
                        features = get_subject_features(
                            s.id, subject.name, performance_score,
                            attendance, per_subject_weekly_hours, difficulty, 30, None
                        )
                        if model and scaler:
                            f_scaled = scaler.transform(np.array([features]))
                            if hasattr(model, "predict_proba"):
                                probs = model.predict_proba(f_scaled)[0]
                                risk_pred = int(np.argmax(probs))
                            else:
                                risk_pred = min(2, max(0, int(model.predict(f_scaled)[0])))
                        else:
                            risk_pred = 1
                        risk_lvl = ["low", "medium", "high"][risk_pred]
                        if prediction_rank.get(risk_lvl, 0) > prediction_rank.get(overall_risk, 0):
                            overall_risk = risk_lvl
                            
                    # Update Prediction table
                    existing = Prediction.query.filter_by(user_id=s.id).order_by(Prediction.date.desc()).first()
                    if existing:
                        existing.predicted_risk_level = overall_risk
                        existing.date = datetime.utcnow()
                    else:
                        new_pred = Prediction(user_id=s.id, predicted_risk_level=overall_risk, date=datetime.utcnow())
                        db.session.add(new_pred)
                    success_count += 1
                except Exception:
                    fail_count += 1
                    
            db.session.commit()
            log_admin_action("batch_ml_prediction", "Prediction", None, f"Triggered batch ML prediction. Success: {success_count}, Fails: {fail_count}")
            flash(f"Batch ML run completed. Success: {success_count}, Skip/Fails: {fail_count}", "success")
            return redirect(url_for("admin.bulk"))
            
        elif action == "bulk_notification":
            target = request.form.get("target")
            cohort = request.form.get("cohort")
            risk_level = request.form.get("risk_level")
            message = request.form.get("message", "").strip()
            
            if not message:
                flash("Notification message cannot be empty.", "warning")
                return redirect(url_for("admin.bulk"))
                
            # Filter users
            query = User.query.filter_by(role="student")
            
            if target == "cohort" and cohort:
                query = query.join(StudentProfile).filter(StudentProfile.study_level == cohort)
            elif target == "risk" and risk_level:
                all_students = query.all()
                filtered_students = []
                for s in all_students:
                    pred = Prediction.query.filter_by(user_id=s.id).order_by(Prediction.date.desc()).first()
                    r_lvl = (pred.predicted_risk_level or "low").lower() if pred else "low"
                    if r_lvl == risk_level.lower():
                        filtered_students.append(s)
                query = filtered_students
                
            # Send notifications
            sent_count = 0
            target_list = query if isinstance(query, list) else query.all()
            for s in target_list:
                notif = Notification(
                    user_id=s.id,
                    message=message,
                    is_read=False,
                    date=datetime.utcnow()
                )
                db.session.add(notif)
                sent_count += 1
                
            db.session.commit()
            log_admin_action("bulk_notification", "Notification", None, f"Sent bulk notification to {sent_count} students (Target: {target})")
            flash(f"Bulk notification sent successfully to {sent_count} students.", "success")
            return redirect(url_for("admin.bulk"))
            
    return render_template("admin/bulk.html", cohorts=levels)


# ── SECTION 4: SYSTEM HEALTH DASHBOARD ───────────────────────────────────────
import os, time, sys
from flask import current_app

# Replace the stub
# (the stub exists from append_stubs.py; Flask will use the LAST registered
#  route for duplicates, but to be safe we'll use a new internal function
#  and route this under /admin/health which the blueprint already has stubs for)


def _check_gemini_api():
    """Ping Gemini with a minimal token to verify the API key is live."""
    try:
        api_key = current_app.config.get("GEMINI_API_KEY", "")
        if not api_key:
            return {"status": "unconfigured", "latency_ms": None, "detail": "No API key set"}
        try:
            from google import genai as _genai
            client = _genai.Client(api_key=api_key)
            start = time.perf_counter()
            resp = client.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents="Reply with exactly: OK",
            )
            latency = round((time.perf_counter() - start) * 1000)
            text = getattr(resp, "text", "") or ""
            return {"status": "ok", "latency_ms": latency, "detail": text.strip()[:80]}
        except ImportError:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.0-flash-lite")
            start = time.perf_counter()
            resp = model.generate_content("Reply with exactly: OK")
            latency = round((time.perf_counter() - start) * 1000)
            return {"status": "ok", "latency_ms": latency, "detail": (resp.text or "")[:80]}
    except Exception as e:
        return {"status": "error", "latency_ms": None, "detail": str(e)[:120]}


def _check_ml_model():
    """Check that the Random Forest model and scaler are loadable."""
    try:
        from app.routes.student import load_ml_model
        model = load_ml_model("random_forest")
        scaler = load_ml_model("scaler")
        if model and scaler:
            return {"status": "ok", "detail": f"RF model: {type(model).__name__}, Scaler: {type(scaler).__name__}"}
        return {"status": "missing", "detail": "Model or scaler not found — train ML first"}
    except Exception as e:
        return {"status": "error", "detail": str(e)[:120]}


def _check_db():
    """Verify database is reachable and return table row counts."""
    try:
        start = time.perf_counter()
        student_count = User.query.filter_by(role="student").count()
        latency = round((time.perf_counter() - start) * 1000)
        pred_count = Prediction.query.count()
        return {"status": "ok", "latency_ms": latency, "detail": f"Students: {student_count}, Predictions: {pred_count}"}
    except Exception as e:
        return {"status": "error", "latency_ms": None, "detail": str(e)[:120]}


def _get_model_config():
    """Return a dict of model config for display."""
    cfg = current_app.config
    return [
        {"label": "MCQ Generator", "model": cfg.get("GEMINI_MODEL_MCQ", "—"), "daily_limit": cfg.get("GEMINI_DAILY_LIMIT_MCQ", "—"), "rpm": cfg.get("GEMINI_RPM_LIMIT_MCQ", "—")},
        {"label": "AI Assistant (Primary)", "model": cfg.get("GEMINI_MODEL_ASSISTANT_PRIMARY", "—"), "daily_limit": cfg.get("GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY", "—"), "rpm": cfg.get("GEMINI_RPM_LIMIT_ASSISTANT_PRIMARY", "—")},
        {"label": "AI Assistant (Fallback)", "model": cfg.get("GEMINI_MODEL_ASSISTANT_FALLBACK", "—"), "daily_limit": cfg.get("GEMINI_DAILY_LIMIT_ASSISTANT_FALLBACK", "—"), "rpm": "—"},
    ]


def _get_disk_info():
    try:
        import shutil
        total, used, free = shutil.disk_usage("/")
        return {
            "total_gb": round(total / 1e9, 1),
            "used_gb": round(used / 1e9, 1),
            "free_gb": round(free / 1e9, 1),
            "pct_used": round(used / total * 100, 1),
        }
    except Exception:
        return {}


def _get_python_info():
    return {
        "version": sys.version.split(" ")[0],
        "executable": sys.executable,
        "platform": sys.platform,
    }



# ── SECTION 2: CONTENT MANAGEMENT ────────────────────────────────────────────

# Replace stub in-place by redefining — Flask will use the last definition
# for the same URL. We reload the blueprint so both definitions register,
# but /admin/content will resolve to this one since blueprints apply routes
# in order. Using url_for('admin.content_subjects') will point here correctly.

from app.models import Subject as SubjectModel

@admin_bp.route("/content/questions")
def content_questions():
    """Browse and delete auto-generated MCQ questions."""
    from app.models import AssessmentQuestion
    page = request.args.get("page", 1, type=int)
    per_page = 30
    subject_id = request.args.get("subject_id", type=int)
    difficulty = request.args.get("difficulty", "").strip()

    q = AssessmentQuestion.query
    if subject_id:
        q = q.filter_by(subject_id=subject_id)
    if difficulty:
        q = q.filter_by(difficulty=difficulty)

    total = q.count()
    from math import ceil
    pages = ceil(total / per_page) if total else 1
    questions = q.order_by(AssessmentQuestion.generated_at.desc()).offset((page-1)*per_page).limit(per_page).all()
    subjects = SubjectModel.query.order_by(SubjectModel.name).all()
    return render_template(
        "admin/content/questions.html",
        questions=questions, subjects=subjects, page=page, pages=pages,
        subject_id=subject_id, difficulty=difficulty, total=total,
    )


@admin_bp.route("/content/questions/<int:q_id>/delete", methods=["POST"])
def content_delete_question(q_id):
    from app.models import AssessmentQuestion
    question = AssessmentQuestion.query.get_or_404(q_id)
    db.session.delete(question)
    db.session.commit()
    log_admin_action("delete_question", "AssessmentQuestion", q_id, f"Deleted MCQ question id={q_id}")
    flash("Question deleted.", "success")
    return redirect(url_for("admin.content_questions"))


@admin_bp.route("/content/chapters")
def content_chapters():
    """Browse chapters by subject."""
    from app.models import Chapter
    subject_id = request.args.get("subject_id", type=int)
    subjects = SubjectModel.query.order_by(SubjectModel.name).all()
    chapters = []
    if subject_id:
        chapters = Chapter.query.filter_by(subject_id=subject_id).order_by(Chapter.chapter_number).all()
    return render_template(
        "admin/content/chapters.html",
        subjects=subjects, chapters=chapters, subject_id=subject_id,
    )


@admin_bp.route("/content/stats")
def content_stats():
    """Content overview stats: subject/chapter/question counts + difficulty breakdown + broken PDFs check."""
    import os
    from app.models import Chapter, AssessmentQuestion, Topic
    from sqlalchemy import func
    subjects = SubjectModel.query.order_by(SubjectModel.name).all()
    rows = []
    for s in subjects:
        ch_count = Chapter.query.filter_by(subject_id=s.id).count()
        q_count = AssessmentQuestion.query.filter_by(subject_id=s.id).count()
        # Difficulty breakdown
        diff_counts = {}
        for diff in ("beginner", "intermediate", "advanced"):
            diff_counts[diff] = AssessmentQuestion.query.filter_by(
                subject_id=s.id, difficulty=diff
            ).count()
        rows.append({
            "subject": s, "chapters": ch_count, "questions": q_count,
            "diff_counts": diff_counts,
        })
    total_questions = AssessmentQuestion.query.count()
    subjects_zero_q = sum(1 for r in rows if r["questions"] == 0)

    # Broken/Blank PDFs scan (< 5KB check)
    broken_pdfs = []
    cache_dir = os.path.join(current_app.root_path, "static", "cache", "pdfs")
    if os.path.exists(cache_dir):
        for f in os.listdir(cache_dir):
            if f.startswith("chapter_") and f.endswith(".pdf"):
                path = os.path.join(cache_dir, f)
                size = os.path.getsize(path)
                if size < 5000:
                    try:
                        tid = int(f.replace("chapter_", "").replace(".pdf", ""))
                        topic = Topic.query.get(tid)
                        broken_pdfs.append({
                            "filename": f,
                            "topic_id": tid,
                            "topic_name": topic.name if topic else "Unknown Topic",
                            "subject_name": topic.chapter.subject.name if topic and topic.chapter and topic.chapter.subject else "Unknown Subject",
                            "size": size
                        })
                    except Exception:
                        pass

    return render_template(
        "admin/content/stats.html",
        rows=rows, total_questions=total_questions,
        subjects_zero_q=subjects_zero_q,
        broken_pdfs=broken_pdfs,
    )


@admin_bp.route("/content/pdfs/regenerate/<int:topic_id>", methods=["POST"])
def content_regenerate_pdf(topic_id):
    """Delete a cached PDF so it will be regenerated on the next download request."""
    import os
    pdf_filename = f"chapter_{topic_id}.pdf"
    cache_dir = os.path.join(current_app.root_path, "static", "cache", "pdfs")
    pdf_path = os.path.join(cache_dir, pdf_filename)
    if os.path.exists(pdf_path):
        try:
            os.remove(pdf_path)
            log_admin_action("delete_cached_pdf", "Topic", topic_id, f"Deleted broken cached PDF '{pdf_filename}' for regeneration")
            flash(f"Deleted cached PDF '{pdf_filename}'. It will be generated fresh upon the next download attempt.", "success")
        except Exception as e:
            flash(f"Error removing cached PDF: {e}", "danger")
    else:
        flash("Cached PDF not found.", "warning")
    return redirect(url_for("admin.content_stats"))




# ── SECTION 2: QUESTION BANK REGENERATION ─────────────────────────────────────

@admin_bp.route("/content/questions/regenerate/<int:subject_id>", methods=["POST"])
def content_regenerate_questions(subject_id):
    """Trigger MCQ regeneration for a subject (respects daily quota)."""
    from app.models import AssessmentQuestion
    from app.services.ai_service import AIService
    subj = SubjectModel.query.get_or_404(subject_id)
    try:
        existing = AssessmentQuestion.query.filter_by(subject_id=subject_id).count()
        ai = AIService()
        ai.generate_assessment_questions(
            subject_name=subj.name,
            level_of_study=subj.level_of_study or "Class 10",
            subject_id=subject_id,
            force_regenerate=False,
        )
        new_count = AssessmentQuestion.query.filter_by(subject_id=subject_id).count()
        added = new_count - existing
        log_admin_action("regenerate_question_bank", "Subject", subject_id,
                         f"Regenerated MCQ bank for '{subj.name}': +{added} questions")
        flash(f"MCQ regeneration done for '{subj.name}'. +{added} new questions.", "success")
    except Exception as e:
        flash(f"Regeneration failed: {e}", "danger")
    return redirect(url_for("admin.content_stats"))


@admin_bp.route("/content/chapters/<int:subject_id>/topics")
def content_chapter_topics(subject_id):
    """List chapters and topics for a subject."""
    from app.models import Chapter, Topic
    subj = SubjectModel.query.get_or_404(subject_id)
    chapters = Chapter.query.filter_by(subject_id=subject_id).order_by(Chapter.chapter_number).all()
    topics_by_chapter = {
        ch.id: Topic.query.filter_by(chapter_id=ch.id).order_by(Topic.topic_number).all()
        for ch in chapters
    }
    return render_template("admin/content/topics.html",
                           subject=subj, chapters=chapters, topics_by_chapter=topics_by_chapter)


# ── SECTION 3: STUDENT SCHEDULE REGENERATE ────────────────────────────────────

@admin_bp.route("/students/<int:student_id>/regenerate-schedule", methods=["POST"])
def student_regenerate_schedule(student_id):
    """Clear study plan so next Planner visit regenerates it."""
    from app.models import StudyPlan, StudentProfile
    student = User.query.get_or_404(student_id)
    profile = StudentProfile.query.filter_by(user_id=student_id).first()
    if not profile:
        flash("Student has no profile.", "warning")
        return redirect(url_for("admin.student_detail", student_id=student_id))
    try:
        StudyPlan.query.filter_by(student_id=student_id).delete()
        db.session.commit()
        log_admin_action("regenerate_schedule", "User", student_id,
                         f"Cleared study plan for {student.email}")
        flash(f"Study plan cleared for {student.full_name or student.email}. "
              "Next Planner visit will regenerate it.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Could not clear schedule: {e}", "danger")
    return redirect(url_for("admin.student_detail", student_id=student_id))


# ── SECTION 4: HEALTH — API USAGE DATA ────────────────────────────────────────

def _get_daily_api_usage():
    from app.models import DailyAPIUsage
    from datetime import date as _date
    today = _date.today()
    rows = DailyAPIUsage.query.filter_by(usage_date=today).all()
    cfg = current_app.config
    limits = {
        "mcq": cfg.get("GEMINI_DAILY_LIMIT_MCQ", 450),
        "assistant": cfg.get("GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY", 45),
    }
    result = []
    for r in rows:
        limit = limits.get(r.feature)
        pct = round(r.call_count / limit * 100, 1) if limit and limit > 0 else None
        result.append({
            "feature": r.feature, "model": r.model_name or "—",
            "count": r.call_count, "limit": limit or "—", "pct": pct,
        })
    return result


# ── SECTION 5: ANALYTICS DETAIL ───────────────────────────────────────────────

@admin_bp.route("/analytics/detail")
def analytics_detail():
    from app.models import StudentProfile, StudyLog, StudentAssessment
    from sqlalchemy import func

    rf_importances = []
    try:
        from app.routes.student import load_ml_model
        model = load_ml_model("random_forest")
        if model and hasattr(model, "feature_importances_"):
            feature_names = [
                "Attendance %", "Assignment Completion %", "Weekly Study Hours",
                "Total Study Hours", "Study Days (240d)", "Subject Difficulty",
                "Avg Exam Score %", "Midterm Score %", "Final Score %",
                "Assignment Avg %", "Year of Study", "Cumulative GPA",
            ]
            combined = sorted(zip(feature_names, model.feature_importances_),
                              key=lambda x: x[1], reverse=True)
            rf_importances = [{"name": n, "importance": round(v * 100, 2)} for n, v in combined]
    except Exception:
        rf_importances = []

    try:
        total_students = User.query.filter_by(role="student", is_active=True).count()
        students_with_logs = db.session.query(StudyLog.user_id).distinct().count()
        adherence_rate = round(students_with_logs / total_students * 100, 1) if total_students else 0.0
    except Exception:
        adherence_rate = 0.0

    try:
        subjects_all = SubjectModel.query.filter_by(is_active=True).order_by(SubjectModel.name).all()
        total_assessed = StudentProfile.query.filter_by(has_completed_assessment=True).count()
        assessment_by_subject = sorted(
            [{"subject": s.name,
              "count": StudentAssessment.query.filter_by(subject_id=s.id).count()}
             for s in subjects_all[:20]],
            key=lambda x: x["count"], reverse=True,
        )
    except Exception:
        assessment_by_subject, total_assessed = [], 0

    missed_topics = []
    try:
        from app.models import AssessmentResponse, AssessmentQuestion
        wrong_counts = (
            db.session.query(
                AssessmentResponse.question_id,
                func.count(AssessmentResponse.id).label("wc"),
            )
            .filter_by(is_correct=False)
            .group_by(AssessmentResponse.question_id)
            .order_by(func.count(AssessmentResponse.id).desc())
            .limit(10)
            .all()
        )
        for qid, cnt in wrong_counts:
            q = AssessmentQuestion.query.get(qid)
            if q:
                missed_topics.append({
                    "question": q.question_text[:100],
                    "subject": q.subject.name if q.subject else "—",
                    "wrong_count": cnt,
                })
    except Exception:
        missed_topics = []

    return render_template(
        "admin/analytics_detail.html",
        rf_importances=rf_importances,
        adherence_rate=adherence_rate,
        assessment_by_subject=assessment_by_subject,
        total_assessed=total_assessed,
        missed_topics=missed_topics,
    )


# ── SECTION 7: CONFIG — STUDY PLANNER SETTINGS ────────────────────────────────

@admin_bp.route("/config/planner", methods=["POST"])
def config_planner():
    from app.models import AppSetting
    for k in ["PLANNER_SESSION_MINUTES", "PLANNER_BREAK_MINUTES", "PLANNER_SESSIONS_PER_DAY"]:
        val = request.form.get(k, "").strip()
        if not val:
            continue
        s = AppSetting.query.get(k)
        if s:
            s.value = val
        else:
            db.session.add(AppSetting(key=k, value=val))
    db.session.commit()
    from app.live_config import load_live_config
    load_live_config(current_app._get_current_object(), force=True)
    log_admin_action("update_planner_config", "AppSetting", None, "Updated Study Planner defaults")
    flash("Study Planner defaults saved.", "success")
    return redirect(url_for("admin.config"))


# ── SECTION 8: BULK-SEED QUESTION BANKS (QUEUED / RATE-LIMITED) ───────────────

import threading as _threading
_bulk_seed_state = {"running": False, "done": 0, "total": 0, "errors": [], "log": []}
_bulk_seed_lock = _threading.Lock()


@admin_bp.route("/bulk/seed-questions", methods=["GET", "POST"])
def bulk_seed_questions():
    from app.models import AssessmentQuestion
    subjects = SubjectModel.query.filter_by(is_active=True).order_by(SubjectModel.name).all()

    if request.method == "POST":
        subject_ids = request.form.getlist("subject_ids", type=int)
        if not subject_ids:
            flash("Select at least one subject.", "warning")
            return redirect(url_for("admin.bulk_seed_questions"))
        with _bulk_seed_lock:
            if _bulk_seed_state["running"]:
                flash("A bulk-seed job is already running.", "warning")
                return redirect(url_for("admin.bulk_seed_questions"))
            _bulk_seed_state.update({
                "running": True, "done": 0, "total": len(subject_ids), "errors": [], "log": [],
            })

        from flask import current_app as _ca
        _app = _ca._get_current_object()

        def _seed_worker(app, ids):
            import time as _time
            with app.app_context():
                from app.models import DailyAPIUsage, AppSetting
                from app.services.ai_service import AIService, QuotaExceededError
                from datetime import date as _d
                ai = AIService()
                for sid in ids:
                    with _bulk_seed_lock:
                        if not _bulk_seed_state["running"]:
                            break
                    subj = SubjectModel.query.get(sid)
                    if not subj:
                        with _bulk_seed_lock:
                            _bulk_seed_state["done"] += 1
                            _bulk_seed_state["errors"].append(f"Subject id={sid} not found")
                        continue
                    try:
                        today = _d.today()
                        used_row = DailyAPIUsage.query.filter_by(
                            feature="mcq", usage_date=today).first()
                        used = used_row.call_count if used_row else 0
                        limit_s = AppSetting.query.get("GEMINI_DAILY_LIMIT_MCQ")
                        limit = int(limit_s.value) if limit_s else app.config.get(
                            "GEMINI_DAILY_LIMIT_MCQ", 450)
                        if used >= limit:
                            msg = f"Daily MCQ quota exhausted ({used}/{limit}). Stopping."
                            with _bulk_seed_lock:
                                _bulk_seed_state["log"].append(msg)
                                _bulk_seed_state["running"] = False
                            break
                        existing = AssessmentQuestion.query.filter_by(subject_id=sid).count()
                        ai.generate_assessment_questions(
                            subject_name=subj.name,
                            level_of_study=subj.level_of_study or "Class 10",
                            subject_id=sid,
                            force_regenerate=False,
                        )
                        new_count = AssessmentQuestion.query.filter_by(subject_id=sid).count()
                        msg = f"+ {subj.name}: +{new_count - existing} questions"
                    except QuotaExceededError:
                        msg = f"- {subj.name}: daily quota hit, stopping"
                        with _bulk_seed_lock:
                            _bulk_seed_state["log"].append(msg)
                            _bulk_seed_state["running"] = False
                        break
                    except Exception as exc:
                        msg = f"- {subj.name}: {str(exc)[:80]}"
                        with _bulk_seed_lock:
                            _bulk_seed_state["errors"].append(msg)
                    with _bulk_seed_lock:
                        _bulk_seed_state["done"] += 1
                        _bulk_seed_state["log"].append(msg)
                    _time.sleep(2)
                with _bulk_seed_lock:
                    _bulk_seed_state["running"] = False

        _threading.Thread(target=_seed_worker, args=(_app, subject_ids), daemon=True).start()
        log_admin_action("bulk_seed_questions", "Subject", None,
                         f"Bulk MCQ seed: {len(subject_ids)} subjects queued")
        flash(f"Bulk seed started for {len(subject_ids)} subjects. Monitor progress below.", "info")
        return redirect(url_for("admin.bulk_seed_questions"))

    with _bulk_seed_lock:
        state = dict(_bulk_seed_state)
    q_counts = {
        s.id: AssessmentQuestion.query.filter_by(subject_id=s.id).count() for s in subjects
    }
    return render_template("admin/bulk_seed.html", subjects=subjects, state=state, q_counts=q_counts)


@admin_bp.route("/bulk/seed-questions/status")
def bulk_seed_status():
    with _bulk_seed_lock:
        return jsonify(dict(_bulk_seed_state))


@admin_bp.route("/bulk/seed-questions/stop", methods=["POST"])
def bulk_seed_stop():
    with _bulk_seed_lock:
        _bulk_seed_state["running"] = False
    flash("Bulk-seed stopped.", "warning")
    return redirect(url_for("admin.bulk_seed_questions"))


# ── SECTION 8: STUDENT DATA EXPORT ────────────────────────────────────────────

@admin_bp.route("/bulk/export-students")
def bulk_export_students():
    import csv
    import io
    from app.models import StudentProfile, StudentAssessment, StudyLog
    from flask import Response
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "user_id", "email", "full_name", "is_active", "date_registered",
        "study_level", "country", "program", "semester", "university",
        "cumulative_gpa", "attendance_pct", "has_completed_assessment",
        "target_weekly_hours", "assessment_count", "study_log_hours",
    ])
    students = User.query.filter_by(role="student").order_by(User.id).all()
    for u in students:
        p = StudentProfile.query.filter_by(user_id=u.id).first()
        a_count = StudentAssessment.query.filter_by(student_id=u.id).count()
        log_hrs = (
            db.session.query(db.func.sum(StudyLog.duration_hours))
            .filter_by(user_id=u.id).scalar() or 0.0
        )
        writer.writerow([
            u.id, u.email, u.full_name or "", u.is_active,
            u.date_registered.strftime("%Y-%m-%d") if u.date_registered else "",
            p.study_level if p else "", p.country if p else "",
            p.program if p else "", p.semester if p else "",
            p.university if p else "",
            p.cumulative_gpa if p else "", p.attendance_pct if p else "",
            p.has_completed_assessment if p else False,
            p.target_weekly_hours if p else "",
            a_count, round(float(log_hrs), 2),
        ])
    log_admin_action("export_students_csv", "User", None,
                     f"Exported {len(students)} students to CSV")
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=students_export.csv"},
    )


@admin_bp.route("/bulk/export-students-json")
def bulk_export_students_json():
    from app.models import StudentProfile, StudentAssessment, StudyLog
    students = User.query.filter_by(role="student").order_by(User.id).all()
    data = []
    for u in students:
        p = StudentProfile.query.filter_by(user_id=u.id).first()
        a_count = StudentAssessment.query.filter_by(student_id=u.id).count()
        log_hrs = (
            db.session.query(db.func.sum(StudyLog.duration_hours))
            .filter_by(user_id=u.id).scalar() or 0.0
        )
        data.append({
            "user_id": u.id, "email": u.email, "full_name": u.full_name,
            "is_active": u.is_active,
            "date_registered": u.date_registered.isoformat() if u.date_registered else None,
            "profile": {
                "study_level": p.study_level, "country": p.country,
                "program": p.program, "semester": p.semester,
                "university": p.university, "cumulative_gpa": p.cumulative_gpa,
                "attendance_pct": p.attendance_pct,
                "has_completed_assessment": p.has_completed_assessment,
                "target_weekly_hours": p.target_weekly_hours,
            } if p else None,
            "assessment_count": a_count,
            "total_study_hours": round(float(log_hrs), 2),
        })
    log_admin_action("export_students_json", "User", None,
                     f"Exported {len(students)} students to JSON")
    return jsonify(data)


# ── SECTION 8: CURRICULUM IMPORT FROM CSV ─────────────────────────────────────

@admin_bp.route("/bulk/import-curriculum", methods=["GET", "POST"])
def bulk_import_curriculum():
    import csv
    import io
    results = []
    if request.method == "POST":
        f = request.files.get("csv_file")
        if not f or not f.filename.lower().endswith(".csv"):
            flash("Please upload a .csv file.", "danger")
            return redirect(url_for("admin.bulk_import_curriculum"))
        stream = io.StringIO(f.stream.read().decode("utf-8-sig"), newline=None)
        reader = csv.DictReader(stream)
        added = skipped = 0
        for row in reader:
            name = (row.get("name") or "").strip()
            if not name:
                continue
            code = (row.get("code") or "").strip() or None
            level = (row.get("level_of_study") or "").strip()
            program = (row.get("program") or "").strip() or None
            semester = (row.get("semester") or "").strip() or None
            try:
                credit_hours = int(row.get("credit_hours") or 3)
                difficulty = int(row.get("difficulty_level") or 3)
            except ValueError:
                credit_hours, difficulty = 3, 3
            exists = SubjectModel.query.filter_by(name=name, level_of_study=level).first()
            if exists:
                results.append({"name": name, "status": "skipped (duplicate)"})
                skipped += 1
                continue
            db.session.add(SubjectModel(
                name=name, code=code, level_of_study=level,
                program=program, semester=semester,
                credit_hours=credit_hours, difficulty_level=difficulty,
                country="Nepal", curriculum="National", is_active=True,
            ))
            results.append({"name": name, "status": "added"})
            added += 1
        db.session.commit()
        log_admin_action("import_curriculum_csv", "Subject", None,
                         f"CSV import: {added} added, {skipped} skipped")
        flash(f"Import complete: {added} subjects added, {skipped} skipped.", "success")
    return render_template("admin/bulk_import.html", results=results)
