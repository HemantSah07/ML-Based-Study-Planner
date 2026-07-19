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
