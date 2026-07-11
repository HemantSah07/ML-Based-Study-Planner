from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify, current_app
from flask_login import login_required, current_user
from app.models import (Prediction, StudyLog, Goal, Subject, AssessmentQuestion, 
                        StudentAssessment, AssessmentResponse, AcademicDocument, 
                        ExtractedMark, StudentProfile, Schedule, Assignment, StudyPlan,
                        Chapter, Topic, Subtopic, LearningMaterial, Flashcard, QuizScore, 
                        StudentNote, LearningProgress, AvailabilitySlot, AIStudyMaterial,
                        SubjectPerformanceHistory, StudentSubject,
                        ReviewedChapter, ChapterQuizScore, BookmarkedChapter, ChapterNote, PastQuestion,
                        StudentSeenQuestion, TopicSeenQuestion, ChapterQuizResult)
from app import db
from datetime import date, datetime, time, timedelta
import joblib
import os
import numpy as np
from app.utils.ocr_processor import MarksheetProcessor
from werkzeug.utils import secure_filename
import json
import re
import io
from difflib import SequenceMatcher
from app.utils.planner_generator import generate_study_planner
from app.utils.timezone_utils import local_now_for_user, local_today_for_user, default_timezone_for_country, MULTI_TIMEZONE_OPTIONS
from app.services.ai_service import ai_service
import logging

logger = logging.getLogger(__name__)

# ── Centralized Student Learning Context ──────────────────────────────────────
# Single source of truth for all student data. Every module reads from and
# writes to this context instead of issuing independent, isolated DB queries.
from app.context.learning_context import get_learning_context

student_bp = Blueprint("student", __name__)

# ── Country → Curriculum mapping (internal only, never shown to user) ─────────
COUNTRY_CURRICULUM_MAP = {
    "Nepal":           "NEB/CTEVT",
    "United States":   "US Common Core/AP",
    "United Kingdom":  "A-Levels/GCSE",
    "South Korea":     "CSAT/National",
    "China":           "Gaokao/National",
    "Germany":         "Abitur/National",
    "Australia":       "HSC/VCE/SACE",
    "Canada":          "Provincial/IB",
    "Japan":           "NSAT/National",
    "Switzerland":     "Matura/National",
    "Singapore":       "A-Levels/IB",
    "Finland":         "Matriculation/National",
    "Netherlands":     "VWO/HAVO",
    "Sweden":          "Gymnasieexamen",
    "Denmark":         "STX/HHX/HTX",
    "Norway":          "Vitnemål",
    "Ireland":         "Leaving Certificate",
    "Belgium":         "CESS/National",
    "France":          "Baccalauréat",
    "Italy":           "Maturità",
    "India":           "CBSE/ICSE/State Boards",
}

# ── Nepal Faculty → Subject-DB level+program mapping ─────────────────────────
# Maps the user-visible Faculty dropdown value to (level_of_study, program) pairs
# that exist in the subjects table, searched in order until a match is found.
NEPAL_FACULTY_SUBJECT_MAP = {
    # Class 11
    "Science Faculty":                              [("Class 11 - Science Stream", "Science Stream"), ("Class 11", "Science Stream")],
    "Management Faculty (Commerce)":                [("Class 11 - Management Stream", "Management Stream"), ("Class 11", "Management")],
    "Humanities and Social Sciences Faculty (Arts)": [("Class 11 - Humanities Stream", "Humanities Stream"), ("Class 11", "Humanities Stream")],
    "Law Faculty":                                  [("Class 11", "Law")],
    "Education Faculty":                            [("Class 11", "Education")],
    # CTEVT technical streams (Class 11/12)
    "Computer Engineering":      [("Class 11", "Computer Engineering")],
    "Civil Engineering":         [("Class 11", "Civil Engineering")],
    "Electrical/Electronics Engineering": [("Class 11", "Electrical Engineering")],
    "Agriculture and Animal Science": [("Class 11", "Agriculture")],
    "Forestry":                  [("Class 11", "Forestry")],
    "Nursing (PCL Nursing)":     [("Class 11", "Nursing")],
    "Pharmacy":                  [("Class 11", "Pharmacy")],
    "Medical Lab Technology (CMLT)": [("Class 11", "CMLT")],
    "Hotel Management & Culinary Arts": [("Class 11", "Hotel Management")],
}
# Equivalent set for Class 12 (same faculty names, different level prefix)
NEPAL_FACULTY_SUBJECT_MAP_C12 = {
    "Science Faculty":                              [("Class 12 - Science Stream", "Science Stream"), ("Class 12 (National Examination Board - NEB)", "Science Stream"), ("Class 12", "Science Stream")],
    "Management Faculty (Commerce)":                [("Class 12 - Management Stream", "Management Stream"), ("Class 12 (National Examination Board - NEB)", "Management"), ("Class 12", "Management")],
    "Humanities and Social Sciences Faculty (Arts)": [("Class 12 - Humanities Stream", "Humanities Stream"), ("Class 12", "Humanities Stream")],
    "Law Faculty":                                  [("Class 12", "Law")],
    "Education Faculty":                            [("Class 12", "Education")],
    "Computer Engineering":      [("Class 12", "Computer Engineering")],
    "Civil Engineering":         [("Class 12", "Civil Engineering")],
    "Electrical/Electronics Engineering": [("Class 12", "Electrical Engineering")],
    "Agriculture and Animal Science": [("Class 12", "Agriculture")],
    "Forestry":                  [("Class 12", "Forestry")],
    "Nursing (PCL Nursing)":     [("Class 12", "Nursing")],
    "Pharmacy":                  [("Class 12", "Pharmacy")],
    "Medical Lab Technology (CMLT)": [("Class 12", "CMLT")],
    "Hotel Management & Culinary Arts": [("Class 12", "Hotel Management")],
}

NEPAL_FIXED_CLASS_SUBJECTS = {
    "Class 9": [
        ("C9-NEP", "Nepali", "Class 9", "General", 4, 3),
        ("C9-ENG", "English", "Class 9", "General", 4, 3),
        ("C9-MATH", "Mathematics", "Class 9", "General", 4, 4),
        ("C9-SCI", "Science", "Class 9", "General", 4, 4),
        ("C9-SOC", "Social Studies", "Class 9", "General", 4, 3),
        ("C9-HPE", "Health and Population", "Class 9", "General", 3, 2),
        ("C9-OPM", "Optional Mathematics", "Class 9", "General", 4, 5),
        ("C9-COM", "Computer Science", "Class 9", "General", 3, 3),
    ],
    "Class 10": [
        ("SEE-NEP", "Nepali", "Class 10 (Secondary Education Examination - SEE)", None, 4, 3),
        ("SEE-ENG", "English", "Class 10 (Secondary Education Examination - SEE)", None, 4, 3),
        ("SEE-MATH", "Mathematics", "Class 10 (Secondary Education Examination - SEE)", None, 4, 4),
        ("SEE-SCI", "Science", "Class 10 (Secondary Education Examination - SEE)", None, 4, 4),
        ("SEE-SOC", "Social Studies", "Class 10 (Secondary Education Examination - SEE)", None, 4, 3),
        ("SEE-OPM", "Optional Mathematics", "Class 10 (Secondary Education Examination - SEE)", None, 4, 5),
    ],
}

SUBJECT_NAME_ALIASES = {
    "scienceandtechnology": "science",
    "socialstudiesandpopulationeducation": "socialstudies",
    "environmentpopulationandhealth": "healthandpopulation",
    "environmenthealthandpopulation": "healthandpopulation",
    "healthphysicalandcreativearts": "healthandpopulation",
    "healthandphysicaleducation": "healthandpopulation",
    "healthphysicaleducation": "healthandpopulation",
    "computer": "computerscience",
    "optionalmath": "optionalmathematics",
    "optmath": "optionalmathematics",
}


def normalize_subject_name(value):
    key = re.sub(r"[^a-z0-9]+", "", (value or "").lower())
    return SUBJECT_NAME_ALIASES.get(key, key)


def _dedupe_subjects_by_name(subjects):
    deduped = []
    seen = set()
    for subject in subjects or []:
        if not subject:
            continue
        key = normalize_subject_name(subject.name)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(subject)
    return deduped


def _ensure_nepal_fixed_subjects(study_level, curriculum):
    specs = NEPAL_FIXED_CLASS_SUBJECTS.get(study_level)
    if not specs:
        return []

    subjects = []
    changed = False
    for code, name, level, program, credit_hours, difficulty in specs:
        subject = Subject.query.filter_by(code=code).first()
        if not subject:
            subject = Subject(code=code)
            db.session.add(subject)
            changed = True

        updates = {
            "name": name,
            "credit_hours": credit_hours,
            "difficulty_level": difficulty,
            "level_of_study": level,
            "program": program,
            "semester": study_level,
            "country": "Nepal",
            "curriculum": curriculum,
        }
        for field, value in updates.items():
            if getattr(subject, field) != value:
                setattr(subject, field, value)
                changed = True
        subjects.append(subject)

    if changed:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    return subjects


def _is_fixed_nepal_class(profile):
    return (
        profile
        and (profile.country or "Nepal").strip() == "Nepal"
        and (profile.study_level or "").strip() in NEPAL_FIXED_CLASS_SUBJECTS
    )


def get_valid_subjects_for_profile(profile):
    """
    Returns the list of Subject objects valid for this student's
    country + study_level + program (Faculty) combination.
    
    For Nepal it resolves the complex level/program naming in the DB.
    For other countries it auto-seeds generic placeholder subjects
    if none exist yet, so the system always has something to show.
    """
    if not profile:
        return []

    country    = (profile.country    or "Nepal").strip()
    study_level = (profile.study_level or "").strip()
    program    = (profile.program    or "").strip()
    curriculum = COUNTRY_CURRICULUM_MAP.get(country, "National")

    # Helper: try a list of (level, prog) pairs, return first match
    def _query(pairs, country_filter=True):
        for lvl, prog in pairs:
            q = Subject.query.filter(Subject.level_of_study == lvl)
            if prog:
                q = q.filter(Subject.program == prog)
            if country_filter:
                q = q.filter((Subject.country == country) | (Subject.country == None))
            results = q.all()
            if results:
                return results
        return []

    subjects = []

    if country == "Nepal":
        lvl = study_level
        if lvl in NEPAL_FIXED_CLASS_SUBJECTS:
            subjects = _ensure_nepal_fixed_subjects(lvl, curriculum)
        elif lvl == "Class 6":
            subjects = _query([("Class 6", None), ("Class 6", "General")])
        elif lvl == "Class 7":
            subjects = _query([("Class 7", None), ("Class 7", "General")])
        elif lvl == "Class 8":
            subjects = _query([("Class 8", None), ("Class 8", "General")])
        elif lvl == "Class 11":
            pairs = NEPAL_FACULTY_SUBJECT_MAP.get(program, [("Class 11", program or None)])
            subjects = _query(pairs)
        elif lvl == "Class 12":
            pairs = NEPAL_FACULTY_SUBJECT_MAP_C12.get(program, [("Class 12", program or None)])
            subjects = _query(pairs)
        elif lvl == "Bachelors":
            subjects = _query([("Bachelor's", program if program else None)])
            # If no match for specific program, seed placeholders for that program
            # (do NOT fall back to all Bachelor's subjects — wrong program mix)
        elif lvl == "Masters":
            subjects = _query([("Master's", program if program else None), ("Master's Level", program if program else None)])
        else:
            # Generic fallback for Nepal
            subjects = Subject.query.filter(
                Subject.level_of_study.ilike(f"%{lvl}%")
            ).all()
    else:
        # Non-Nepal: try exact match first
        subjects = Subject.query.filter(
            Subject.country == country,
            Subject.level_of_study == study_level
        ).all()

    # If still nothing found, auto-seed generic placeholders
    if not subjects:
        subjects = _seed_placeholder_subjects(country, study_level, program, curriculum)

    return _dedupe_subjects_by_name(subjects)


def _seed_placeholder_subjects(country, study_level, program, curriculum):
    """
    Inserts generic placeholder Subject rows for country+level+program
    combos not yet in the DB, then returns them.
    This keeps the subject picker functional for any combination.
    """
    lvl = study_level
    prog = program or "General"
    prefix = f"{country[:3].upper()}-{lvl[:3].upper().replace(' ', '')}-{prog[:3].upper()}"

    if lvl in ["Bachelors", "Masters"]:
        if prog and prog not in ["", "General"]:
            names = [f"{prog} Core I", f"{prog} Core II", f"{prog} Core III", "Research Methodology", "Elective Course"]
        else:
            names = ["Major Core I", "Major Core II", "Research Methods", "Elective I", "Elective II"]
        db_level = "Bachelor's" if lvl == "Bachelors" else "Master's"
        db_prog  = prog
    elif lvl in ["Class 11", "Class 12"]:
        names = ["Mathematics", "English", "Core Subject I", "Core Subject II", "Optional Subject"]
        db_level = lvl
        db_prog  = prog
    else:
        names = ["Mathematics", "Science", "English", "Social Studies",
                 "Nepali" if country == "Nepal" else "Second Language"]
        db_level = lvl
        db_prog  = "General"

    placeholders = []
    for i, name in enumerate(names, 1):
        code = f"{prefix}-{i}"
        existing = Subject.query.filter_by(code=code).first()
        if existing:
            placeholders.append(existing)
            continue
        sub = Subject(
            code=code,
            name=name,
            level_of_study=db_level,
            program=db_prog,
            country=country,
            curriculum=curriculum,
            credit_hours=3,
            difficulty_level=3,
        )
        db.session.add(sub)
        placeholders.append(sub)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    return placeholders


def get_subject_performance_snapshot(user_id, subject_id):
    """
    Retrieves the assessment/performance score (0-100) for a student and subject.
    Sources:
    1. Latest ExtractedMark for this subject (from uploaded marksheets).
    2. Latest StudentAssessment (quiz) score and/or Chapter quiz scores.
    Missing data returns None so the predictor can disable that subject.
    """
    subj = Subject.query.get(subject_id)
    if subj:
        latest_mark = (
            ExtractedMark.query
            .join(AcademicDocument)
            .filter(AcademicDocument.student_id == user_id)
            .filter((ExtractedMark.subject_name_mapped == subj.name) | (ExtractedMark.subject_name_original == subj.name))
            .order_by(AcademicDocument.uploaded_at.desc())
            .first()
        )
        if latest_mark and latest_mark.percentage is not None:
            return {
                "score": max(0.0, min(100.0, float(latest_mark.percentage))),
                "source": "marksheet",
                "source_label": "from marksheet",
            }

    assessment_score = None
    latest_quiz = (
        StudentAssessment.query
        .filter_by(student_id=user_id, subject_id=subject_id)
        .order_by(StudentAssessment.completed_at.desc())
        .first()
    )
    if latest_quiz:
        if getattr(latest_quiz, 'weighted_score', 0) > 0:
            assessment_score = latest_quiz.weighted_score
        else:
            assessment_score = latest_quiz.total_score

    chapter_quizzes = ChapterQuizScore.query.join(Topic).join(Chapter).filter(
        ChapterQuizScore.student_id == user_id,
        Chapter.subject_id == subject_id
    ).all()
    avg_chapter_score = None
    if chapter_quizzes:
        percentages = [(cs.score / cs.total_questions) * 100.0 for cs in chapter_quizzes]
        avg_chapter_score = sum(percentages) / len(percentages)

    final_quiz_score = None
    source_label = ""
    if assessment_score is not None and avg_chapter_score is not None:
        final_quiz_score = (assessment_score + avg_chapter_score) / 2.0
        source_label = "from assessment & chapter quizzes"
    elif assessment_score is not None:
        final_quiz_score = assessment_score
        source_label = "from assessment"
    elif avg_chapter_score is not None:
        final_quiz_score = avg_chapter_score
        source_label = "from chapter quizzes"

    if final_quiz_score is not None:
        return {
            "score": max(0.0, min(100.0, float(final_quiz_score))),
            "source": "assessment",
            "source_label": source_label,
        }

    return {
        "score": None,
        "source": "missing",
        "source_label": "No assessment",
    }


def get_subject_performance_score(user_id, subject_id):
    return get_subject_performance_snapshot(user_id, subject_id)["score"]

def grade_from_score(score):
    if score >= 90.0: return "A"
    if score >= 85.0: return "A-"
    if score >= 80.0: return "B+"
    if score >= 75.0: return "B"
    if score >= 70.0: return "B-"
    if score >= 65.0: return "C+"
    if score >= 60.0: return "C"
    if score >= 50.0: return "C-"
    return "F"


def latest_prediction_rows(user_id):
    """Return one latest prediction row per subject from raw_inputs JSON."""
    latest_by_subject = {}
    predictions = Prediction.query.filter_by(user_id=user_id).order_by(Prediction.date.desc()).all()
    for pred in predictions:
        try:
            raw = json.loads(pred.raw_inputs or "{}")
        except Exception:
            raw = {}
        subject_name = raw.get("subject_name")
        if not subject_name or subject_name in latest_by_subject:
            continue
        latest_by_subject[subject_name] = {
            "subject_name": subject_name,
            "subject_id": raw.get("subject_id"),
            "performance_score": float(raw.get("performance_score", pred.avg_exam_score_pct or 0.0)),
            "attendance": float(raw.get("attendance", pred.attendance_pct or 90.0)),
            "weekly_study_hours": float(raw.get("weekly_study_hours", pred.weekly_study_hours or 14.0)),
            "subject_difficulty": float(raw.get("subject_difficulty", pred.subject_difficulty or 3.0)),
            "days_until_exam": int(raw.get("days_until_exam", 30)),
            "days_since_last_studied": int(raw.get("days_since_last_studied", 7)),
            "risk_score": float(raw.get("risk_score", 0.5)),
            "risk_pct": float(raw.get("risk_pct", 50.0)),
            "risk_level": pred.predicted_risk_level,
            "prediction_result": ["Pass", "At Risk", "Fail"][{"low": 0, "medium": 1, "high": 2}.get(pred.predicted_risk_level, 1)],
        }
    return list(latest_by_subject.values())


def load_ml_model(model_name):
    path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '../../models', f'{model_name}.pkl')
    try:
        return joblib.load(path)
    except Exception:
        return None


def get_level_slug(lvl_string):
    if not lvl_string:
        return "bachelors"
    lvl = lvl_string.lower()
    if "class 8" in lvl:
        return "class8"
    elif "see" in lvl or "class 10" in lvl:
        return "see"
    elif "class 11" in lvl:
        return "class11"
    elif "class 12" in lvl:
        return "class12"
    elif "bachelor" in lvl:
        return "bachelors"
    elif "master" in lvl:
        return "masters"
    return "bachelors"


def get_subject_features(user_id, subject_name, input_grade, input_attendance, input_weekly_hours, input_difficulty, input_days_until_exam=30, input_days_since_last_studied=None):
    """Build the 7-feature vector used by the Random Forest model."""
    subject = Subject.query.filter_by(name=subject_name).first()
    subject_id = subject.id if subject else None
    today_local = local_today_for_user(user_id)

    # ── Feature 1: previous_grade ─────────────────────────────────────────────
    previous_grade = float(input_grade)

    # ── Feature 2: attendance ─────────────────────────────────────────────────
    attendance = float(input_attendance)

    # ── Feature 3: difficulty ─────────────────────────────────────────────────
    difficulty = float(input_difficulty)

    # ── Feature 4: study_hours (weekly) ──────────────────────────────────────
    study_hours = float(input_weekly_hours)

    # ── Feature 5: days_until_exam ────────────────────────────────────────────
    days_until_exam = int(input_days_until_exam) if input_days_until_exam is not None else 30
    # Try to derive from Exam table if possible
    if subject_id:
        try:
            from app.models import Exam
            upcoming_exams = Exam.query.filter(
                Exam.user_id == user_id,
                Exam.subject_id == subject_id,
                Exam.date >= today_local
            ).order_by(Exam.date.asc()).all()
            if upcoming_exams:
                days_until_exam = (upcoming_exams[0].date - today_local).days
        except Exception:
            pass
    days_until_exam = max(0, min(90, days_until_exam))

    # ── Feature 6: days_since_last_studied ────────────────────────────────────
    days_since_last_studied = int(input_days_since_last_studied) if input_days_since_last_studied is not None else 7
    if input_days_since_last_studied is None and subject_id:
        try:
            last_log = StudyLog.query.filter_by(
                user_id=user_id, subject_id=subject_id
            ).order_by(StudyLog.date.desc()).first()
            last_review = ReviewedChapter.query.join(Topic).join(Chapter).filter(ReviewedChapter.student_id == user_id, Chapter.subject_id == subject_id, ReviewedChapter.status == "completed").order_by(ReviewedChapter.last_accessed_at.desc()).first()
            if (last_log and last_log.date) or last_review:
                # last_review query already run above
                last_review_date = last_review.last_accessed_at.date() if (last_review and last_review.last_accessed_at) else None
                last_log_date = last_log.date if (last_log and last_log.date) else None
                most_recent_date = max(last_log_date, last_review_date) if (last_log_date and last_review_date) else (last_log_date or last_review_date)
                delta = today_local - most_recent_date if most_recent_date else timedelta(days=7)
                days_since_last_studied = max(0, delta.days)
        except Exception:
            pass
    days_since_last_studied = min(60, days_since_last_studied)

    # ── Feature 7: completion_rate (prior week plan vs actual) ────────────────
    completion_rate = 1.0  # optimistic default
    if subject_id:
        try:
            week_ago = today_local - timedelta(days=7)
            history = SubjectPerformanceHistory.query.filter(
                SubjectPerformanceHistory.user_id == user_id,
                SubjectPerformanceHistory.subject_name == subject_name,
                SubjectPerformanceHistory.week_start >= week_ago
            ).order_by(SubjectPerformanceHistory.logged_at.desc()).first()
            if history:
                completion_rate = float(history.completion_rate)
        except Exception:
            pass

    features = [
        previous_grade,          # 0: previous_grade
        attendance,              # 1: attendance
        difficulty,              # 2: difficulty
        study_hours,             # 3: study_hours
        float(days_until_exam),  # 4: days_until_exam
        float(days_since_last_studied),  # 5: days_since_last_studied
        completion_rate,         # 6: completion_rate
    ]
    return features



def get_level_slug(lvl_string):
    """Convert a study_level string to a model filename slug."""
    if not lvl_string:
        return "bachelors"
    lvl_lower = lvl_string.lower()
    if "class 6" in lvl_lower or "class 7" in lvl_lower:
        return "see"   # use same model as lower school
    if "class 8" in lvl_lower:
        return "class8"
    if "class 9" in lvl_lower:
        return "see"
    if "class 10" in lvl_lower or "see" in lvl_lower:
        return "see"
    if "class 11" in lvl_lower:
        return "class11"
    if "class 12" in lvl_lower or "neb" in lvl_lower:
        return "class12"
    if lvl_lower == "bachelors" or "bachelor" in lvl_lower:
        return "bachelors"
    if lvl_lower == "masters" or "master" in lvl_lower:
        return "masters"
    if "university" in lvl_lower or "year" in lvl_lower:
        return "bachelors"
    return "bachelors"


def get_profile_subjects(profile):
    """Return subjects the student has selected, seeding from valid curriculum if none yet."""
    if not profile:
        return []

    from app.models import StudentSubject

    if not profile.study_level:
        return []

    valid_subs = get_valid_subjects_for_profile(profile)
    valid_by_key = {normalize_subject_name(s.name): s for s in valid_subs}
    valid_by_id = {s.id: s for s in valid_subs}
    enforce_full_curriculum = _is_fixed_nepal_class(profile)

    user_subs = StudentSubject.query.filter_by(user_id=profile.user_id).all()
    selected_subjects = []
    seen_keys = set()
    changed = False

    for mapping in user_subs:
        subject = mapping.subject
        if not subject:
            db.session.delete(mapping)
            changed = True
            continue

        key = normalize_subject_name(subject.name)
        canonical_subject = valid_by_key.get(key)
        if not canonical_subject or key in seen_keys:
            db.session.delete(mapping)
            changed = True
            continue

        if mapping.subject_id != canonical_subject.id:
            mapping.subject_id = canonical_subject.id
            changed = True

        selected_subjects.append(canonical_subject)
        seen_keys.add(key)

    if enforce_full_curriculum:
        for subject in valid_subs:
            key = normalize_subject_name(subject.name)
            if key in seen_keys:
                continue
            db.session.add(StudentSubject(user_id=profile.user_id, subject_id=subject.id))
            selected_subjects.append(subject)
            seen_keys.add(key)
            changed = True

    if selected_subjects:
        if changed:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
        return _dedupe_subjects_by_name(selected_subjects)

    for ds in valid_subs:
        if ds.id in valid_by_id:
            mapping = StudentSubject(user_id=profile.user_id, subject_id=ds.id)
            db.session.add(mapping)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    return valid_subs

@student_bp.route("/dashboard")
@login_required
def dashboard():
    if current_user.role != 'student':
        return redirect(url_for('admin.dashboard'))

    # ── Centralized context — single source of truth for this request ─────────
    ctx = get_learning_context(current_user.id)

    # Subject hours chart — read from context
    subject_hours = ctx.subject_hours_chart
    chart_labels = list(subject_hours.keys())
    chart_data = list(subject_hours.values())
    total_scheduled = sum(chart_data)

    # Assignment completion — read from context
    assignment_completion = ctx.assignment_completion

    # Risk counts — read from context
    risk = ctx.schedule_risk_counts
    high_risk, medium_risk, low_risk = risk["high"], risk["medium"], risk["low"]

    # Recommendations — read from context (risk-based + weak-subject aware)
    recs = ctx.recommendations

    # Today's tasks — read from context
    today_slots = ctx.current_tasks
    today_idx = local_now_for_user(current_user.id).weekday()

    # Study hours & streak — read from context
    logged_hours = ctx.study_hours
    streak = ctx.streak

    # Achievements — read from context (assessment + quiz + lesson completions)
    accomplishments = ctx.achievements

    # Recommended topics for revision — read from context (based on weak chapters)
    recommended_topics = ctx.recommended_topics

    # Run study log analysis against planner targets
    from app.utils.log_analyzer import analyze_student_logs
    log_analysis = None
    try:
        log_analysis = analyze_student_logs(current_user.id)
    except Exception:
        pass

    # 5. Bookmarked chapters recommendation if days_until_exam is under 7 days
    from app.models import Exam, BookmarkedChapter
    today_local = local_today_for_user(current_user.id)
    week_away = today_local + timedelta(days=7)
    
    upcoming_exams = Exam.query.filter(
        Exam.user_id == current_user.id,
        Exam.date >= today_local,
        Exam.date <= week_away
    ).all()
    urgent_subject_ids = [ex.subject_id for ex in upcoming_exams]
    
    recommended_review_bookmarks = []
    if urgent_subject_ids:
        recommended_review_bookmarks = BookmarkedChapter.query.join(Topic).join(Chapter).filter(
            BookmarkedChapter.student_id == current_user.id,
            Chapter.subject_id.in_(urgent_subject_ids)
        ).all()
        
    recent_study_history = ReviewedChapter.query.filter_by(
        student_id=current_user.id
    ).order_by(ReviewedChapter.last_accessed_at.desc()).limit(5).all()

    # Weekly commitments category summary widget
    slots = AvailabilitySlot.query.filter_by(user_id=current_user.id).all()
    commitment_summary = {}
    for s in slots:
        cat = s.category or s.slot_type or "Other"
        try:
            sh = int(s.start_time.split(":")[0]) * 60 + int(s.start_time.split(":")[1])
            eh = int(s.end_time.split(":")[0]) * 60 + int(s.end_time.split(":")[1])
            dur = ((1440 - sh) + eh) / 60.0 if sh > eh else (eh - sh) / 60.0
        except Exception:
            dur = 0.0
        commitment_summary[cat] = commitment_summary.get(cat, 0.0) + dur
    for cat in list(commitment_summary.keys()):
        commitment_summary[cat] = round(commitment_summary[cat], 1)
    available_study_hours = round(get_available_study_hours_total(current_user.id), 1)

    return render_template("student/dashboard.html",
                           user=current_user,
                           profile=ctx.profile,
                           today_idx=today_idx,
                           logged_hours=logged_hours,
                           log_analysis=log_analysis,
                           streak=streak,
                           accomplishments=accomplishments[:4],
                           recommended_topics=recommended_topics,
                           commitment_summary=commitment_summary,
                           available_study_hours=available_study_hours,
                           chart_labels=chart_labels,
                           chart_data=chart_data,
                           total_scheduled=total_scheduled,
                           risk_data=[high_risk, medium_risk, low_risk],
                           today_slots=today_slots,
                           recommended_review_bookmarks=recommended_review_bookmarks,
                           recent_study_history=recent_study_history)

@student_bp.route("/evaluation", methods=["GET", "POST"])
@login_required
def evaluation():
    flash("The legacy ML Evaluation simulator has been replaced by the Random Forest Predictor.", "info")
    return redirect(url_for("student.predict"))

    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    if request.method == "POST":
        try:
            features = [
                float(request.form.get("attendance_pct", 0)),
                float(request.form.get("assignment_completion_pct", 0)),
                float(request.form.get("weekly_study_hours", 0)),
                float(request.form.get("total_logged_study_hours", 0)),
                int(request.form.get("study_days_last_240", 0)),
                float(request.form.get("subject_difficulty", 0)),
                float(request.form.get("avg_exam_score_pct", 0)),
                float(request.form.get("midterm_score_pct", 0)),
                float(request.form.get("final_score_pct", 0)),
                float(request.form.get("assignment_avg_pct", 0)),
                int(request.form.get("year_of_study", 1)),
                float(request.form.get("cumulative_gpa", 0))
            ]

            model = load_ml_model("random_forest")
            scaler = load_ml_model('scaler')
            
            if model and scaler:
                f_array = np.array([features])
                f_scaled = scaler.transform(f_array)
                risk_pred = model.predict(f_scaled)[0]
                
                # Dynamic and realistic predicted grade calculation
                gpa = features[11]
                avg_exam = features[6]
                assignments = features[1]
                attendance = features[0]
                
                # Weight elements realistically to estimate academic score (0-100)
                perf_score = 0.4 * (gpa * 25.0) + 0.3 * avg_exam + 0.2 * assignments + 0.1 * attendance
                
                if perf_score >= 90.0:
                    predicted_grade = "A"
                elif perf_score >= 85.0:
                    predicted_grade = "A-"
                elif perf_score >= 80.0:
                    predicted_grade = "B+"
                elif perf_score >= 75.0:
                    predicted_grade = "B"
                elif perf_score >= 70.0:
                    predicted_grade = "B-"
                elif perf_score >= 65.0:
                    predicted_grade = "C+"
                elif perf_score >= 60.0:
                    predicted_grade = "C"
                elif perf_score >= 50.0:
                    predicted_grade = "C-"
                else:
                    predicted_grade = "F"
                    
                risk_level = ["low", "medium", "high"][min(2, max(0, int(risk_pred)))]
            else:
                risk_level = "medium"
                predicted_grade = "B"
                flash("Model not trained yet, using placeholder prediction.", "warning")
            
            pred_record = Prediction(
                user_id=current_user.id,
                attendance_pct=features[0],
                assignment_completion_pct=features[1],
                weekly_study_hours=features[2],
                total_logged_study_hours=features[3],
                study_days_last_240=features[4],
                subject_difficulty=features[5],
                avg_exam_score_pct=features[6],
                midterm_score_pct=features[7],
                final_score_pct=features[8],
                assignment_avg_pct=features[9],
                year_of_study=features[10],
                cumulative_gpa=features[11],
                predicted_risk_level=risk_level,
                predicted_grade=predicted_grade
            )
            db.session.add(pred_record)
            db.session.commit()
            
            flash("Prediction generated successfully!", "success")
        except Exception as e:
            flash(f"Error making prediction: {str(e)}", "danger")
            
    past_predictions = Prediction.query.filter_by(user_id=current_user.id).order_by(Prediction.date.desc()).all()
    docs = AcademicDocument.query.filter_by(student_id=current_user.id).order_by(AcademicDocument.uploaded_at.desc()).all()
    latest_prediction = past_predictions[0] if past_predictions else None
    avg_confidence = (
        round(sum(d.extraction_confidence for d in docs) / len(docs) * 100, 1) if docs else 0
    )
    return render_template(
        "student/evaluation.html",
        past_predictions=past_predictions,
        latest_prediction=latest_prediction,
        profile=profile,
        documents=docs,
        doc_count=len(docs),
        avg_confidence=avg_confidence,
    )

@student_bp.route("/study_log", methods=["GET", "POST"])
@login_required
def study_log():
    # ── Context: shared learning state for this request
    ctx = get_learning_context(current_user.id)

    if request.method == "POST":
        duration = request.form.get("duration_hours")
        notes_text = request.form.get("notes")
        subject_id = request.form.get("subject_id")

        if duration:
            # If a specific subject was chosen by id, log by name lookup;
            # otherwise fall back to direct DB insert with subject_id
            subj_name = None
            sub_id_int = None
            if subject_id and subject_id.isdigit():
                sub_id_int = int(subject_id)
                s = Subject.query.get(sub_id_int)
                subj_name = s.name if s else None

            if subj_name:
                # ── Context mutation: log_study_hours invalidates study_hours/streak/recent_activity
                log = StudyLog(
                    user_id=current_user.id,
                    date=local_today_for_user(current_user.id),
                    duration_hours=float(duration),
                    notes=notes_text,
                    subject_id=sub_id_int,
                )
                db.session.add(log)
                db.session.commit()
                # Invalidate context caches after direct write
                ctx._study_logs = None
                ctx._streak = None
                ctx._recent_activity = None
            else:
                log = StudyLog(
                    user_id=current_user.id,
                    date=local_today_for_user(current_user.id),
                    duration_hours=float(duration),
                    notes=notes_text,
                    subject_id=sub_id_int,
                )
                db.session.add(log)
                db.session.commit()
                ctx._study_logs = None
                ctx._streak = None
                ctx._recent_activity = None

            flash("Study log added!", "success")

    # Read from context — already aggregated, no extra queries
    logs = StudyLog.query.filter_by(user_id=current_user.id).order_by(StudyLog.date.desc()).all()
    total_logged = ctx.study_hours
    subjects = ctx.subjects

    return render_template("student/study_log.html", logs=logs, total_logged=total_logged, subjects=subjects)

@student_bp.route("/schedule", methods=["GET"])
@login_required
def schedule():
    # ── Context: read schedule data from shared state
    ctx = get_learning_context(current_user.id)

    weekly_schedule = ctx.weekly_schedule
    risk = ctx.schedule_risk_counts
    total_week_hours = ctx.total_week_hours
    schedules = ctx._schedule_list  # reuse already-loaded list for count

    subjects = ctx.subjects
    today_idx = local_now_for_user(current_user.id).weekday()

    return render_template(
        "student/schedule.html",
        weekly_schedule=weekly_schedule,
        subjects=subjects,
        today_idx=today_idx,
        total_week_hours=total_week_hours,
        schedule_count=len(schedules),
        risk_counts=risk,
        profile=ctx.profile,
        get_subject_performance_score=get_subject_performance_score,
    )

@student_bp.route("/api/risk-analysis", methods=["POST"])
@login_required
def risk_analysis():
    if request.is_json:
        data = request.json
        subjects_list = data.get("subjects", [])
    else:
        subject_names = request.form.getlist("subject_name[]")
        previous_grades = request.form.getlist("previous_grade[]")
        attendances = request.form.getlist("attendance[]")
        study_hours = request.form.getlist("study_hours[]")
        difficulties = request.form.getlist("difficulty[]")
        exam_days_list = request.form.getlist("days_until_exam[]")
        
        subjects_list = []
        for i in range(len(subject_names)):
            subjects_list.append({
                "name": subject_names[i],
                "previous_grade": float(previous_grades[i]) if previous_grades[i] else 70.0,
                "attendance": float(attendances[i]) if attendances[i] else 85.0,
                "study_hours": float(study_hours[i]) if study_hours[i] else 6.0,
                "difficulty": float(difficulties[i]) if difficulties[i] else 3.0,
                "days_until_exam": int(exam_days_list[i]) if i < len(exam_days_list) and exam_days_list[i] else 30,
            })
            
    if not subjects_list:
        return jsonify({"status": "error", "message": "No subjects provided for analysis."}), 400
        
    model = load_ml_model('random_forest')
    scaler = load_ml_model('scaler')
    if not model or not scaler:
        return jsonify({"status": "error", "message": "ML Risk prediction models are not trained yet."}), 500
        
    results = []
    total_allocated_hours = 0.0
    
    for s in subjects_list:
        name = s.get("name")
        grade = s.get("previous_grade", 70.0)
        att = s.get("attendance", 85.0)
        hrs = s.get("study_hours", 6.0)
        diff = s.get("difficulty", 3.0)
        exam_days = s.get("days_until_exam", 30)
        
        features = get_subject_features(current_user.id, name, grade, att, hrs, diff, exam_days)
        
        f_scaled = scaler.transform([features])

        # ── Use predict_proba for continuous risk score ───────────────────────
        risk_score = 0.5  # fallback
        risk_pred = 1     # fallback medium
        if hasattr(model, "predict_proba"):
            try:
                probs = model.predict_proba(f_scaled)[0]  # [P_low, P_med, P_high]
                # risk_score is the weighted mean: 0*P_low + 0.5*P_med + 1.0*P_high
                risk_score = float(0.0 * probs[0] + 0.5 * probs[1] + 1.0 * probs[2])
                risk_pred = int(np.argmax(probs))
            except Exception:
                risk_pred = int(model.predict(f_scaled)[0])
        else:
            risk_pred = int(model.predict(f_scaled)[0])

        # Boost risk score by 15% if last completion_rate < 0.7
        try:
            week_ago = local_today_for_user(current_user.id) - timedelta(days=7)
            history = SubjectPerformanceHistory.query.filter(
                SubjectPerformanceHistory.user_id == current_user.id,
                SubjectPerformanceHistory.subject_name == name,
                SubjectPerformanceHistory.week_start >= week_ago
            ).order_by(SubjectPerformanceHistory.logged_at.desc()).first()
            if history and history.completion_rate < 0.7:
                risk_score = min(1.0, risk_score * 1.15)
        except Exception:
            pass

        risk_pct = round(risk_score * 100, 1)
        
        risk_label = "Low"
        if risk_score >= 0.6:
            risk_label = "High"
        elif risk_score >= 0.35:
            risk_label = "Medium"
            
        # Proportional hour allocation based on continuous risk score (0–1)
        base = 1.0 + (diff * 0.4)          # low-risk baseline
        extra = risk_score * (diff * 0.8)   # added hours for risk
        allocated = base + extra
            
        total_allocated_hours += allocated
        
        results.append({
            "name": name,
            "risk_numeric": risk_pred,
            "risk_level": risk_label,
            "risk_score": round(risk_score, 3),
            "risk_pct": risk_pct,
            "allocated_hours": round(allocated, 1)
        })
        
    available_hours = get_available_study_hours_total(current_user.id)
            
    warning = ""
    if total_allocated_hours > available_hours:
        warning = f"⚠️ Alert: Recommended study hours ({round(total_allocated_hours, 1)} hrs) exceed your available weekly study slots ({round(available_hours, 1)} hrs). Please configure more study slots in your availability dashboard."
        
    return jsonify({
        "status": "success",
        "analysis": results,
        "total_allocated_hours": round(total_allocated_hours, 1),
        "available_hours": round(available_hours, 1),
        "warning": warning
    })



@student_bp.route("/schedule/generate", methods=["POST"])
@login_required
def generate_schedule():
    subject_names   = request.form.getlist("subject_name[]")
    previous_grades = request.form.getlist("previous_grade[]")
    attendances     = request.form.getlist("attendance[]")
    study_hours     = request.form.getlist("study_hours[]")
    difficulties    = request.form.getlist("difficulty[]")
    exam_days_list  = request.form.getlist("days_until_exam[]")

    if not subject_names:
        rows = latest_prediction_rows(current_user.id)
        subject_names = [row["subject_name"] for row in rows]
        previous_grades = [str(row["performance_score"]) for row in rows]
        attendances = [str(row["attendance"]) for row in rows]
        study_hours = [str(row["weekly_study_hours"]) for row in rows]
        difficulties = [str(row["subject_difficulty"]) for row in rows]
        exam_days_list = [str(row["days_until_exam"]) for row in rows]

    if not subject_names:
        flash("Run ML Predictor for at least one assessed subject before generating a schedule.", "warning")
        return redirect(url_for('student.schedule'))

    # ── 1. Snapshot previous week actual hours for feedback loop ──────────────
    today_local = local_today_for_user(current_user.id)
    week_start = today_local - timedelta(days=today_local.weekday())  # Monday
    for i, name in enumerate(subject_names):
        try:
            subj_obj = Subject.query.filter_by(name=name).first()
            subject_id = subj_obj.id if subj_obj else None
            grade = float(previous_grades[i]) if i < len(previous_grades) else 70.0
            att   = float(attendances[i])      if i < len(attendances)     else 85.0
            hrs   = float(study_hours[i])      if i < len(study_hours)     else 6.0
            diff  = float(difficulties[i])     if i < len(difficulties)    else 3.0
            exam_d = int(exam_days_list[i])    if i < len(exam_days_list) and exam_days_list[i] else 30

            # How many hours did student actually log this past week?
            prev_week_start = week_start - timedelta(days=7)
            actual_hours = 0.0
            if subject_id:
                logs_this_week = StudyLog.query.filter(
                    StudyLog.user_id == current_user.id,
                    StudyLog.subject_id == subject_id,
                    StudyLog.date >= prev_week_start,
                    StudyLog.date < week_start
                ).all()
                actual_hours = sum(l.duration_hours for l in logs_this_week if l.duration_hours)

            # What was planned last week? Check last history record
            last_hist = SubjectPerformanceHistory.query.filter(
                SubjectPerformanceHistory.user_id == current_user.id,
                SubjectPerformanceHistory.subject_name == name,
                SubjectPerformanceHistory.week_start == prev_week_start
            ).first()
            planned_hours = last_hist.planned_hours if last_hist else hrs

            completion_rate = min(1.0, actual_hours / planned_hours) if planned_hours > 0 else 1.0

            # Get days_since_last_studied
            days_since = 7
            if subject_id:
                last_log = StudyLog.query.filter_by(
                    user_id=current_user.id, subject_id=subject_id
                ).order_by(StudyLog.date.desc()).first()
                if last_log and last_log.date:
                    days_since = max(0, (today_local - last_log.date).days)

            # risk score for history (use predict_proba)
            risk_score_hist = 0.5
            try:
                model_h  = load_ml_model('random_forest')
                scaler_h = load_ml_model('scaler')
                if model_h and scaler_h:
                    feat_h = get_subject_features(current_user.id, name, grade, att, hrs, diff, exam_d)
                    fs_h = scaler_h.transform([feat_h])
                    probs_h = model_h.predict_proba(fs_h)[0]
                    risk_score_hist = float(0.0*probs_h[0] + 0.5*probs_h[1] + 1.0*probs_h[2])
            except Exception:
                pass

            hist_record = SubjectPerformanceHistory(
                user_id=current_user.id,
                week_start=week_start,
                subject_name=name,
                grade=grade, attendance=att, difficulty=diff,
                study_hours=hrs, days_until_exam=exam_d,
                days_since_last_studied=days_since,
                planned_hours=planned_hours, actual_hours=actual_hours,
                completion_rate=completion_rate, risk_score=risk_score_hist
            )
            db.session.add(hist_record)
        except Exception:
            pass
    db.session.flush()

    # ── 2. Clear existing schedule ────────────────────────────────────────────
    Schedule.query.filter_by(user_id=current_user.id).delete()

    model  = load_ml_model('random_forest')
    scaler = load_ml_model('scaler')
    if not model or not scaler:
        flash("Machine Learning models are not trained yet!", "danger")
        return redirect(url_for('student.schedule'))

    # ── 3. Predict risk & compute per-subject allocated hours ─────────────────
    subject_data = []
    total_recommended_hours = 0.0

    for i in range(len(subject_names)):
        name  = subject_names[i]
        grade = float(previous_grades[i]) if i < len(previous_grades) else 70.0
        att   = float(attendances[i])      if i < len(attendances)     else 85.0
        hrs   = float(study_hours[i])      if i < len(study_hours)     else 6.0
        diff  = float(difficulties[i])     if i < len(difficulties)    else 3.0
        exam_d = int(exam_days_list[i])    if i < len(exam_days_list) and exam_days_list[i] else 30

        features = get_subject_features(current_user.id, name, grade, att, hrs, diff, exam_d)
        f_scaled = scaler.transform([features])

        # Continuous risk score via predict_proba
        risk_score = 0.5
        risk_pred  = 1
        if hasattr(model, "predict_proba"):
            try:
                probs = model.predict_proba(f_scaled)[0]
                risk_score = float(0.0*probs[0] + 0.5*probs[1] + 1.0*probs[2])
                risk_pred  = int(np.argmax(probs))
            except Exception:
                risk_pred = int(model.predict(f_scaled)[0])
        else:
            risk_pred = int(model.predict(f_scaled)[0])

        # Boost score if low completion history
        try:
            week_ago = local_today_for_user(current_user.id) - timedelta(days=7)
            hist = SubjectPerformanceHistory.query.filter(
                SubjectPerformanceHistory.user_id == current_user.id,
                SubjectPerformanceHistory.subject_name == name,
                SubjectPerformanceHistory.week_start >= week_ago
            ).order_by(SubjectPerformanceHistory.logged_at.desc()).first()
            if hist and hist.completion_rate < 0.7:
                risk_score = min(1.0, risk_score * 1.15)
        except Exception:
            pass

        # Proportional hours: risk_score in [0,1] maps to hours in [base, base+max_extra]
        MAX_DAILY_CAP = 3.0  # maximum hours per subject per day
        base  = 1.0 + (diff * 0.4)
        extra = risk_score * (diff * 0.8)
        allocated = base + extra

        risk_label = "Low Risk"
        if risk_score >= 0.6:
            risk_label = "High Risk"
        elif risk_score >= 0.35:
            risk_label = "Medium Risk"

        total_recommended_hours += allocated

        subj = Subject.query.filter_by(name=name).first()
        if not subj:
            subj = Subject(name=name, difficulty_level=int(diff))
            db.session.add(subj)
            db.session.flush()

        subject_data.append({
            'id': subj.id,
            'name': name,
            'risk': risk_pred,
            'risk_label': risk_label,
            'risk_score': risk_score,
            'score': risk_score * diff,
            'allocated_hours': allocated,
        })

    logger.info(
        "Schedule generation subjects considered user=%s subjects=%s",
        current_user.id,
        [
            {
                "name": sd["name"],
                "risk_score": round(sd["risk_score"], 3),
                "risk_label": sd["risk_label"],
                "allocated_hours": round(sd["allocated_hours"], 2),
            }
            for sd in subject_data
        ],
    )

    # ── 4. Parse availability slots from JSON submitted by form ───────────────
    free_slots_json = request.form.get("free_slots_json", "{}")
    raw_slots = {}
    try:
        raw_slots = json.loads(free_slots_json)
    except Exception:
        pass

    DAYS_MAP = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
        'Friday': 4, 'Saturday': 5, 'Sunday': 6
    }

    # Build per-day lists of free hours. Study time is derived as time not covered
    # by Sleep/Class/Sports/Social/Entertainment/Personal/Other commitments.
    day_study_hours = {i: [] for i in range(7)}
    day_blocked_hours = {i: set() for i in range(7)}  # Sleep/Busy hours

    for key, status in raw_slots.items():
        if "-" not in key:
            continue
        parts    = key.split("-")
        day_name = parts[0]
        if day_name not in DAYS_MAP:
            continue
        try:
            hour    = int(parts[1])
            day_idx = DAYS_MAP[day_name]
            if status == "free":
                day_study_hours[day_idx].append(hour)
            elif status in ("sleep", "busy"):
                day_blocked_hours[day_idx].add(hour)
        except ValueError:
            pass

    # Use DB-derived inverse availability as the source of truth.
    db_available_hours = get_available_study_hours_by_day(current_user.id)
    for i in range(7):
        raw_free = set(day_study_hours[i]) if any(day_study_hours.values()) else set(db_available_hours[i])
        day_study_hours[i] = sorted(raw_free - day_blocked_hours[i])

    logger.info(
        "Schedule generation availability user=%s available_hours_by_day=%s",
        current_user.id,
        {day: len(hours) for day, hours in day_study_hours.items()},
    )

    has_any_slots = any(len(hrs) > 0 for hrs in day_study_hours.values())

    if has_any_slots:
        # ── 5. Round-Robin daily-capacity allocator ───────────────────────────
        # Sort subjects: highest risk_score first
        sorted_subjects = sorted(subject_data, key=lambda x: x['risk_score'], reverse=True)

        # Per-subject remaining hours to schedule
        remaining = {sd['name']: max(1, int(round(sd['allocated_hours']))) for sd in sorted_subjects}
        MAX_DAILY_CAP = 3.0  # max hours per subject per day

        scheduled_slots = []  # list of (day_idx, hour, subject_dict)

        # Round-robin: cycle through days, then subjects
        # We keep iterating until all hours are allocated or we exhaust slots
        days_with_slots = [d for d in range(7) if day_study_hours[d]]
        day_hour_pointer = {d: 0 for d in days_with_slots}  # index into sorted hour list
        day_subject_hours_today = {d: {} for d in range(7)}  # track hours per subject per day

        subject_cursor = 0
        total_target_slots = min(
            sum(remaining.values()),
            sum(len(hours) for hours in day_study_hours.values())
        )
        max_passes = max(1, len(days_with_slots) * max(1, len(sorted_subjects)) * 4)
        passes = 0
        while len(scheduled_slots) < total_target_slots and passes < max_passes:
            passes += 1
            progress = False
            for day_idx in days_with_slots:
                if len(scheduled_slots) >= total_target_slots:
                    break
                ptr = day_hour_pointer[day_idx]
                if ptr >= len(day_study_hours[day_idx]):
                    continue
                for offset in range(len(sorted_subjects)):
                    subj_idx = (subject_cursor + offset) % len(sorted_subjects)
                    sd = sorted_subjects[subj_idx]
                    name = sd['name']
                    if remaining[name] <= 0:
                        continue
                    already_today = day_subject_hours_today[day_idx].get(name, 0.0)
                    if already_today >= MAX_DAILY_CAP:
                        continue
                    hour = day_study_hours[day_idx][ptr]
                    scheduled_slots.append((day_idx, hour, sd))
                    day_hour_pointer[day_idx] += 1
                    day_subject_hours_today[day_idx][name] = already_today + 1.0
                    remaining[name] -= 1
                    subject_cursor = (subj_idx + 1) % len(sorted_subjects)
                    progress = True
                    break
            if not progress:
                break  # no more slots to fill

        # ── 6. Validation check ───────────────────────────────────────────────
        total_available = sum(len(h) for h in day_study_hours.values())
        subjects_in_plan = set(s[2]['name'] for s in scheduled_slots)
        all_subjects_present = all(sd['name'] in subjects_in_plan for sd in subject_data)
        total_planned = len(scheduled_slots)
        within_tolerance = abs(total_planned - total_recommended_hours) <= (total_recommended_hours * 0.25 + 1)

        logger.info(
            "Schedule generation allocation summary user=%s target_slots=%s planned_slots=%s all_subjects_present=%s within_tolerance=%s remaining=%s per_day_subject_hours=%s",
            current_user.id,
            total_target_slots,
            total_planned,
            all_subjects_present,
            within_tolerance,
            remaining,
            day_subject_hours_today,
        )

        # ── 7. Write schedule to DB ───────────────────────────────────────────
        for (day_idx, hour, sd) in scheduled_slots:
            tip = "Focus on intense practice & review" if sd['risk'] == 2 else "Maintain current study habits"
            new_schedule = Schedule(
                user_id=current_user.id,
                day_of_week=day_idx,
                start_time=time(hour, 0),
                end_time=time((hour + 1) % 24, 0),
                subject_id=sd['id'],
                description=f"[{sd['risk_label']}] - {tip}"
            )
            db.session.add(new_schedule)

        # Update planned hours in performance history
        planned_by_subject = {}
        for (_, __, sd) in scheduled_slots:
            planned_by_subject[sd['name']] = planned_by_subject.get(sd['name'], 0) + 1.0
        for h_rec in SubjectPerformanceHistory.query.filter_by(
            user_id=current_user.id, week_start=week_start
        ).all():
            if h_rec.subject_name in planned_by_subject:
                h_rec.planned_hours = planned_by_subject[h_rec.subject_name]

    else:
        # Fallback: sequential scheduling when no availability grid was provided
        current_day  = 0
        current_hour = 17

        for sd in subject_data:
            assigned_hours = max(1, int(round(sd['allocated_hours'])))
            tip = "Focus on intense practice & review" if sd['risk'] == 2 else "Maintain current study habits"

            while assigned_hours > 0:
                if current_hour >= 23:
                    current_day  = (current_day + 1) % 7
                    current_hour = 17 if current_day < 5 else 10

                slot_duration   = min(2, assigned_hours)
                end_hour        = current_hour + slot_duration
                actual_end_hour = min(end_hour, 23)
                actual_end_min  = 59 if end_hour >= 24 else 0

                new_schedule = Schedule(
                    user_id=current_user.id,
                    day_of_week=current_day,
                    start_time=time(current_hour, 0),
                    end_time=time(actual_end_hour, actual_end_min),
                    subject_id=sd['id'],
                    description=f"[{sd['risk_label']}] - {tip}"
                )
                db.session.add(new_schedule)
                current_hour   = end_hour + 1
                assigned_hours -= slot_duration

    db.session.commit()
    flash("Adaptive Study Plan generated successfully based on ML predictions!", "success")
    return redirect(url_for('student.schedule'))


def generate_assessment_questions_for_subject(subject_id):
    from app.services.ai_service import ai_service
    
    subject = Subject.query.get(subject_id)
    if not subject:
        return 0
        
    # Get chapters/topics of this subject to help link questions
    chapters = Chapter.query.filter_by(subject_id=subject_id).all()
    ch_info = ""
    ch_map = {}
    if chapters:
        ch_info = "The chapters/topics for this subject are:\n"
        for ch in chapters:
            ch_info += f"- Chapter {ch.chapter_number}: {ch.name}\n"
            topics = Topic.query.filter_by(chapter_id=ch.id).all()
            for t in topics:
                ch_info += f"  - Topic {t.topic_number}: {t.name}\n"
                ch_map[t.name.lower()] = (ch.id, t.id)
                ch_map[ch.name.lower()] = (ch.id, t.id)
                
    # 1 & 2: Fetch previously answered questions to avoid repetition
    seen_qs_text = []
    if current_user and current_user.is_authenticated:
        seen_q_ids = [sq.question_id for sq in StudentSeenQuestion.query.filter_by(student_id=current_user.id).all()]
        if seen_q_ids:
            seen_qs = AssessmentQuestion.query.filter(
                AssessmentQuestion.id.in_(seen_q_ids),
                AssessmentQuestion.subject_id == subject_id
            ).all()
            seen_qs_text = [q.question_text for q in seen_qs]
            
    exclusion_text = ""
    if seen_qs_text:
        # Just send a subset if it's too large to save tokens
        exclusion_text = "\nDo not repeat any of these questions:\n" + "\n".join(f"- {q}" for q in seen_qs_text[-50:])

    prompt = (
        f"Generate exactly 15 high-quality, distinct multiple-choice questions covering the core syllabus topics of the subject '{subject.name}' "
        f"for a student in '{subject.level_of_study}' under the '{subject.program or 'General'}' program.\n"
        f"Curriculum context: Nepal NEB or equivalent college level standards.\n\n"
        f"{ch_info}\n"
        "Requirements:\n"
        "1. Generate exactly 5 'easy', 5 'medium', and 5 'hard' questions.\n"
        "2. Each question must have 4 options (A, B, C, D) and one correct answer.\n"
        "3. Provide distinct, subject-relevant, non-repetitive questions. Do NOT repeat classic boilerplate questions.\n"
        "4. Map each question to a chapter number and topic name from the list above if possible.\n"
        f"{exclusion_text}"
    )
    
    system_instruction = "You are an expert examiner for the National Examination Board (NEB) of Nepal."
    
    response_schema = {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "q": {"type": "STRING", "description": "Question text"},
                "a": {"type": "STRING"},
                "b": {"type": "STRING"},
                "c": {"type": "STRING"},
                "d": {"type": "STRING"},
                "ans": {"type": "STRING", "description": "Correct option: A, B, C, or D"},
                "diff": {"type": "STRING", "description": "easy, medium, or hard"},
                "type": {"type": "STRING"},
                "ch_num": {"type": "INTEGER"},
                "topic_name": {"type": "STRING"},
                "explanation": {"type": "STRING", "description": "Explanation of the correct answer"}
            },
            "required": ["q", "a", "b", "c", "d", "ans", "diff", "explanation"]
        }
    }
    
    try:
        response_text = ai_service.generate_content(
            prompt, 
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=response_schema
        )
        questions_data = parse_json_safely(response_text)
    except Exception as e:
        print(f"Error calling AI / parsing JSON: {e}")
        return 0
    
    count = 0
    if isinstance(questions_data, list):
        # Part B: Additive generation. DO NOT delete old questions!
        # Fetch existing questions to avoid near-duplicates
        existing_qs = [q.question_text.lower()[:50] for q in AssessmentQuestion.query.filter_by(subject_id=subject_id).all()]
        
        for q in questions_data:
            # Validation
            q_text = q.get("q", "")
            if not q_text or len(q_text) < 10:
                continue
            if q_text.lower()[:50] in existing_qs:
                continue # Skip near-duplicates
                
            opt_a = q.get("a")
            opt_b = q.get("b")
            opt_c = q.get("c")
            opt_d = q.get("d")
            correct = q.get("ans", q.get("correct_answer", q.get("correct", "")))
            if not all([opt_a, opt_b, opt_c, opt_d]) or correct.upper() not in ["A", "B", "C", "D"]:
                continue

            # Map chapter and topic
            chapter_id = None
            topic_id = None
            
            # Find matching chapter/topic from our map
            t_name = str(q.get("topic_name", "")).lower()
            ch_num = q.get("ch_num")
            
            # Try to match topic name
            matched = False
            for key, val in ch_map.items():
                if key in t_name or t_name in key:
                    chapter_id, topic_id = val
                    matched = True
                    break
                    
            if not matched and chapters:
                # Try to match by chapter number
                for ch in chapters:
                    if ch.chapter_number == ch_num:
                        chapter_id = ch.id
                        first_topic = Topic.query.filter_by(chapter_id=ch.id).first()
                        if first_topic:
                            topic_id = first_topic.id
                        break
                # Fallback to first chapter/topic
                if not chapter_id:
                    chapter_id = chapters[0].id
                    first_topic = Topic.query.filter_by(chapter_id=chapters[0].id).first()
                    if first_topic:
                        topic_id = first_topic.id
            
            diff_val = q.get("diff", q.get("difficulty", "medium"))
            type_val = q.get("type", q.get("question_type", "conceptual"))
            
            new_q = AssessmentQuestion(
                subject_id=subject_id,
                chapter_id=chapter_id,
                topic_id=topic_id,
                question_text=q_text,
                option_a=opt_a,
                option_b=opt_b,
                option_c=opt_c,
                option_d=opt_d,
                correct_answer=correct.upper(),
                difficulty=diff_val.lower(),
                question_type=type_val,
                source="ai_generated"
            )
            db.session.add(new_q)
            count += 1
            
        db.session.commit()
    return count


# --- ASSESSMENT ROUTES ---

@student_bp.route("/assessment/start", methods=["GET", "POST"])
@login_required
def assessment_start():
    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    
    if not profile or not profile.study_level:
        flash("Please set your class level first", "warning")
        return redirect(url_for("student.profile"))
        
    subjects = get_profile_subjects(profile)
    active_subject_ids = {s.id for s in subjects}
    preselected_subject_id = request.args.get("subject_id", type=int)
    if preselected_subject_id and preselected_subject_id in active_subject_ids:
        subjects = [s for s in subjects if s.id == preselected_subject_id]

    if request.method == "POST":
        selected_subjects = []
        for raw_id in request.form.getlist("subjects"):
            try:
                sub_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if sub_id in active_subject_ids:
                selected_subjects.append(sub_id)

        if not selected_subjects:
            flash("Please select at least one active profile subject.", "warning")
            return redirect(url_for('student.assessment_start'))
            
        # Ensure we have enough unseen questions
        for sub_id in selected_subjects:
            seen_subquery = db.session.query(StudentSeenQuestion.question_id).filter_by(student_id=current_user.id)
            unseen_count = AssessmentQuestion.query.filter(
                AssessmentQuestion.subject_id == sub_id,
                ~AssessmentQuestion.id.in_(seen_subquery)
            ).count()
            
            if unseen_count < 15:
                generate_assessment_questions_for_subject(sub_id)

        session['assessment_subjects'] = selected_subjects
        session['assessment_current_idx'] = 0
        session['assessment_scores'] = {}
        session['assessment_history'] = {} # Track correct/wrong per subject for adaptive difficulty
        session['assessment_question_history'] = {} # Track detailed question outcomes
        
        # Clear difficulty state
        for sub_id in selected_subjects:
            session.pop(f'assessment_diff_{sub_id}', None)
        
        first_sub = session['assessment_subjects'][0]
        return redirect(url_for('student.assessment_question', subject_id=first_sub, q_num=1))
        
    return render_template(
        "student/assessment_start.html",
        subjects=subjects,
        profile=profile,
        preselected_subject_id=preselected_subject_id,
    )

@student_bp.route("/assessment/question/<int:subject_id>/<int:q_num>")
@login_required
def assessment_question(subject_id, q_num):
    # Total 12 questions per subject (Adaptive Assessment)
    if q_num > 12:
        # Move to next subject
        subs = session.get('assessment_subjects', [])
        idx = session.get('assessment_current_idx', 0) + 1
        if idx < len(subs):
            session['assessment_current_idx'] = idx
            return redirect(url_for('student.assessment_question', subject_id=subs[idx], q_num=1))
        else:
            return redirect(url_for('student.assessment_results'))
            
    # Adaptive logic
    history = session.get('assessment_history', {}).get(str(subject_id), [])
    current_diff = session.get(f'assessment_diff_{subject_id}', 'medium')
    
    if len(history) >= 2:
        last_two = history[-2:]
        if last_two == [True, True]:
            if current_diff == 'easy': current_diff = 'medium'
            elif current_diff == 'medium': current_diff = 'hard'
        elif last_two == [False, False]:
            if current_diff == 'hard': current_diff = 'medium'
            elif current_diff == 'medium': current_diff = 'easy'
            
    session[f'assessment_diff_{subject_id}'] = current_diff
    
    # Pick an unseen question
    import random
    seen_subquery = db.session.query(StudentSeenQuestion.question_id).filter_by(student_id=current_user.id)
    questions = AssessmentQuestion.query.filter(
        AssessmentQuestion.subject_id == subject_id,
        AssessmentQuestion.difficulty == current_diff,
        ~AssessmentQuestion.id.in_(seen_subquery)
    ).all()
    
    if not questions:
        # Fallback to any difficulty unseen
        questions = AssessmentQuestion.query.filter(
            AssessmentQuestion.subject_id == subject_id,
            ~AssessmentQuestion.id.in_(seen_subquery)
        ).all()
        
    if not questions:
        # Absolute fallback
        questions = AssessmentQuestion.query.filter_by(subject_id=subject_id).all()
        
    q = random.choice(questions) if questions else None
    
    if not q:
        flash("No assessment questions found for this subject. Ensure databases are seeded.", "danger")
        return redirect(url_for('student.assessment_start'))
    
    subject = Subject.query.get(subject_id)
    return render_template("student/assessment_question.html", question=q, subject=subject, q_num=q_num, total_q=12)

@student_bp.route("/assessment/answer", methods=["POST"])
@login_required
def assessment_answer():
    q_id = int(request.form.get("question_id"))
    sub_id = int(request.form.get("subject_id"))
    q_num = int(request.form.get("q_num"))
    answer = request.form.get("answer")
    time_taken = int(request.form.get("time_taken", 0))
    
    q = AssessmentQuestion.query.get(q_id)
    is_correct = (answer == q.correct_answer)
    
    # Log to StudentSeenQuestion
    seen_q = StudentSeenQuestion(
        student_id=current_user.id,
        question_id=q_id,
        was_correct=is_correct
    )
    db.session.add(seen_q)
    db.session.commit()
    
    # Track history
    history = session.get('assessment_history', {})
    if str(sub_id) not in history:
        history[str(sub_id)] = []
    history[str(sub_id)].append(is_correct)
    session['assessment_history'] = history
    
    # Track detailed question history
    q_history = session.get('assessment_question_history', {})
    q_history[str(q_id)] = is_correct
    session['assessment_question_history'] = q_history
    
    # Track score
    scores = session.get('assessment_scores', {})
    if str(sub_id) not in scores:
        scores[str(sub_id)] = {'correct': 0, 'total': 0, 'weighted_points': 0, 'max_points': 0}
    
    scores[str(sub_id)]['total'] += 1
    
    weight = 1.0
    diff = (q.difficulty or "").lower()
    if diff == "medium" or diff == "intermediate": weight = 1.5
    if diff == "hard" or diff == "advanced": weight = 2.0
    
    scores[str(sub_id)]['max_points'] += weight
    if is_correct:
        scores[str(sub_id)]['correct'] += 1
        scores[str(sub_id)]['weighted_points'] += weight
        
    session['assessment_scores'] = scores
    
    return redirect(url_for('student.assessment_question', subject_id=sub_id, q_num=q_num + 1))

@student_bp.route("/assessment/results")
@login_required
def assessment_results():
    scores = session.get('assessment_scores', {})
    q_history = session.get('assessment_question_history', {})

    # ── Context: persist results and derive weak/strong areas ────────────────
    ctx = get_learning_context(current_user.id)

    # Delegate DB writes to context (StudentAssessment rows + profile flag)
    avg_score = ctx.update_assessment_results(scores, q_history)

    # Build display results list from scores dict
    results = []
    for sub_id, data in scores.items():
        total_q = data.get('total', 12)
        flat_pct = (data['correct'] / total_q) * 100 if total_q > 0 else 0
        
        # Weighted scoring calculation
        w_pts = data.get('weighted_points', 0)
        m_pts = data.get('max_points', total_q)
        weighted_pct = (w_pts / m_pts) * 100 if m_pts > 0 else 0
        
        tier = 'beginner'
        if weighted_pct >= 70: tier = 'advanced'
        elif weighted_pct >= 40: tier = 'intermediate'
        
        subj = Subject.query.get(int(sub_id))
        results.append({
            'subject': subj.name if subj else 'Unknown',
            'score': weighted_pct, # Display weighted percentage
            'flat_score': flat_pct,
            'tier': tier,
            'correct': data['correct'],
            'total': total_q
        })

    # Weak chapters & recommended topics — read from context (avoids re-querying)
    weak_chapters = ctx.weak_chapters
    recommended_topics = ctx.weak_topics

    # Build revision plan steps from weak topics
    revision_plan_steps = []
    for ch_info in weak_chapters:
        topics = Topic.query.filter_by(chapter_id=ch_info["id"]).all()
        for t in topics:
            revision_plan_steps.append(
                f"Revise textbook material for '{t.name}' under "
                f"Chapter {ch_info['chapter_number']} of {ch_info['subject_name']} "
                f"for 45 mins. Log it in study log."
            )

    # Study time suggestions per subject
    study_times = []
    for sub_id, data in scores.items():
        subj = Subject.query.get(int(sub_id))
        if not subj:
            continue
        pct = (data['correct'] / 15.0) * 100 if data.get('total', 0) > 0 else 0
        if pct < 40:
            rec_hours = "3.0 hours/day (High priority)"
        elif pct < 70:
            rec_hours = "2.0 hours/day (Medium priority)"
        else:
            rec_hours = "1.0 hour/day (Low priority)"
        study_times.append({
            "subject_name": subj.name,
            "score": pct,
            "recommended_hours": rec_hours,
        })

    return render_template(
        "student/assessment_results.html",
        results=results,
        avg_score=avg_score,
        weak_chapters=weak_chapters,
        recommended_topics=recommended_topics[:6],
        revision_plan_steps=revision_plan_steps[:4],
        study_times=study_times,
    )


# --- DOCUMENT UPLOAD ROUTES ---

@student_bp.route("/documents/upload", methods=["POST"])
@login_required
def upload_document():
    if 'document_file' not in request.files:
        flash("No file part", "danger")
        return redirect(url_for('student.evaluation'))
        
    file = request.files['document_file']
    if file.filename == '':
        flash("No selected file", "danger")
        return redirect(url_for('student.evaluation'))
        
    if file:
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        if ext not in ['pdf', 'jpg', 'jpeg', 'png']:
            flash("Invalid file type. Only PDF and Images allowed.", "danger")
            return redirect(url_for('student.evaluation'))

        flash("Please use ML Predictor > Upload Marksheet to review and confirm OCR results before saving.", "warning")
        return redirect(url_for('student.predict'))
            
        upload_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), '../../app/static/uploads', str(current_user.id))
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)
        
        doc_type = request.form.get("document_type")
        inst_name = request.form.get("institution_name")
        exam_year = int(request.form.get("exam_year", 2020))
        
        # Process OCR
        file_type = 'pdf' if ext == 'pdf' else 'image'
        processor = MarksheetProcessor()
        
        try:
            marks_data, confidence = processor.process_file(filepath, file_type)
        except Exception as e:
            # Handle timeout/failure
            doc = AcademicDocument(
                student_id=current_user.id, document_type=doc_type, document_name=filename,
                file_path=filepath, file_type=ext, institution_name=inst_name, exam_year=exam_year,
                overall_percentage=0, extraction_confidence=0, processed_at=datetime.utcnow()
            )
            db.session.add(doc)
            db.session.commit()
            flash(f"Processing failed: {str(e)}", "danger")
            return redirect(url_for('student.evaluation'))
        
        doc = AcademicDocument(
            student_id=current_user.id, document_type=doc_type, document_name=filename,
            file_path=filepath, file_type=ext, institution_name=inst_name, exam_year=exam_year,
            extraction_confidence=confidence, processed_at=datetime.utcnow()
        )
        db.session.add(doc)
        db.session.flush()
        
        total_pct = 0
        count = 0
        for m in marks_data:
            pct = processor.convert_to_percentage(m['value'], m['full_marks'])
            mapped_subject = map_to_active_subject_name(current_user.id, m['subject'])
            em = ExtractedMark(
                document_id=doc.id, subject_name_original=m['subject'],
                subject_name_mapped=mapped_subject,
                marks_obtained=float(m['value']) if m['value'].replace('.','',1).isdigit() else 0,
                full_marks=float(m['full_marks']), percentage=pct, grade=m['value'] if not m['value'].replace('.','',1).isdigit() else ""
            )
            db.session.add(em)
            total_pct += pct
            count += 1
            
        overall = total_pct / count if count > 0 else 0
        doc.overall_percentage = overall
        
        # Update Profile
        profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
        if profile:
            profile.documents_uploaded += 1
            weight = 0.2
            if doc_type in ['see_class10', 'plus_two', 'a_level']: weight = 0.4
            
            if profile.prior_academic_score == 0:
                profile.prior_academic_score = overall
            else:
                profile.prior_academic_score = (profile.prior_academic_score * (1 - weight)) + (overall * weight)
                
            if profile.prior_academic_score >= 80: profile.academic_level = 'excellent'
            elif profile.prior_academic_score >= 65: profile.academic_level = 'good'
            elif profile.prior_academic_score >= 50: profile.academic_level = 'average'
            else: profile.academic_level = 'weak'
            
        db.session.commit()
        flash(f"Document uploaded! Extracted {count} subjects.", "success")
        return redirect(url_for('student.evaluation'))

@student_bp.route("/documents/<int:doc_id>")
@login_required
def document_detail(doc_id):
    doc = AcademicDocument.query.get_or_404(doc_id)
    if doc.student_id != current_user.id:
        return redirect(url_for('student.evaluation'))
    marks = ExtractedMark.query.filter_by(document_id=doc.id).all()
    return render_template("student/document_detail.html", document=doc, marks=marks)

@student_bp.route("/documents/<int:doc_id>/delete", methods=["POST"])
@login_required
def delete_document(doc_id):
    doc = AcademicDocument.query.get_or_404(doc_id)
    if doc.student_id == current_user.id:
        ExtractedMark.query.filter_by(document_id=doc.id).delete()
        db.session.delete(doc)
        db.session.commit()
        try:
            if os.path.exists(doc.file_path):
                os.remove(doc.file_path)
        except Exception as e:
            flash("Error deleting document.", "danger")
        flash("Document deleted.", "success")
    return redirect(url_for('student.evaluation'))


# --- NEW OCR & PREDICTION ROUTES ---

@student_bp.route("/predict", methods=["GET", "POST"])
@login_required
def predict():
    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    student_subjects = get_profile_subjects(profile)
    active_by_id = {s.id: s for s in student_subjects}
    doc_count = AcademicDocument.query.filter_by(student_id=current_user.id).count()
    subject_snapshots = []
    for subject in student_subjects:
        snap = get_subject_performance_snapshot(current_user.id, subject.id)
        subject_snapshots.append({
            "subject": subject,
            "score": snap["score"],
            "source": snap["source"],
            "source_label": snap["source_label"],
            "has_real_score": snap["source"] != "missing",
        })
    eligible_subject_count = sum(1 for item in subject_snapshots if item["has_real_score"])

    def render_predict(**kwargs):
        context = {
            "profile": profile,
            "doc_count": doc_count,
            "student_subjects": student_subjects,
            "subject_snapshots": subject_snapshots,
            "eligible_subject_count": eligible_subject_count,
            "is_ocr": False,
            "selected_subject_ids": [],
            "batch_results": [],
            "skipped_subjects": [],
        }
        context.update(kwargs)
        return render_template("student/predict.html", **context)

    if request.method == "POST":
        try:
            selected_ids = []
            for raw_id in request.form.getlist("subject_ids[]"):
                try:
                    subject_id = int(raw_id)
                except (TypeError, ValueError):
                    continue
                if subject_id in active_by_id and subject_id not in selected_ids:
                    selected_ids.append(subject_id)

            if not selected_ids:
                flash("Select at least one profile subject.", "warning")
                return render_predict()

            # Convert GPA (0–4 scale) to percentage (0–100) for ML model
            raw_gpa = float(
                profile.cumulative_gpa
                if profile and profile.cumulative_gpa is not None
                else (profile.prior_academic_score if profile and profile.prior_academic_score else 0.0)
            )
            # Values ≤ 4.0 are on GPA scale; values > 4 are already percentages (legacy data)
            profile_grade = raw_gpa * 25 if raw_gpa <= 4.0 else raw_gpa
            attendance = float(profile.attendance_pct if profile and profile.attendance_pct is not None else 85.0)
            target_weekly_hours = float(profile.target_weekly_hours if profile and profile.target_weekly_hours else 14.0)
            per_subject_weekly_hours = max(1.0, target_weekly_hours / max(1, len(student_subjects)))
            model = load_ml_model("random_forest")
            scaler = load_ml_model("scaler")
            if not model or not scaler:
                flash("Random Forest model not trained yet, using fallback prediction.", "warning")

            batch_results = []
            skipped_subjects = []
            session_subjects = []
            session_marks = []
            prediction_rank = {"low": 0, "medium": 1, "high": 2}
            highest_result = "Pass"

            for subject_id in selected_ids:
                subject = active_by_id[subject_id]
                snapshot = get_subject_performance_snapshot(current_user.id, subject.id)
                if snapshot["source"] == "missing" or snapshot["score"] is None:
                    skipped_subjects.append({
                        "subject": subject.name,
                        "reason": f"Skipped: {subject.name} (no assessment found)",
                    })
                    continue

                performance_score = snapshot["score"]
                difficulty = float(subject.difficulty_level or 3.0)
                features = get_subject_features(
                    current_user.id,
                    subject.name,
                    performance_score,
                    attendance,
                    per_subject_weekly_hours,
                    difficulty,
                    30,
                    None,
                )
                days_until_exam = int(features[4])
                days_since_last_studied = int(features[5])

                confidence = 85.0
                risk_score = 0.5
                if model and scaler:
                    f_scaled = scaler.transform(np.array([features]))
                    if hasattr(model, "predict_proba"):
                        probs = model.predict_proba(f_scaled)[0]
                        risk_score = float(0.0 * probs[0] + 0.5 * probs[1] + 1.0 * probs[2])
                        risk_pred = int(np.argmax(probs))
                        confidence = round(float(np.max(probs)) * 100, 1)
                    else:
                        risk_pred = min(2, max(0, int(model.predict(f_scaled)[0])))
                        risk_score = [0.1, 0.5, 0.9][risk_pred]
                else:
                    risk_pred = 1

                risk_level = ["low", "medium", "high"][risk_pred]
                prediction_result = ["Pass", "At Risk", "Fail"][risk_pred]
                if prediction_rank[risk_level] > prediction_rank.get(highest_result.lower().replace("at risk", "medium").replace("pass", "low").replace("fail", "high"), 0):
                    highest_result = prediction_result
                risk_pct = round(risk_score * 100, 1)
                predicted_grade = grade_from_score(performance_score)

                raw_inputs = {
                    "subject_id": subject.id,
                    "subject_name": subject.name,
                    "performance_score": performance_score,
                    "performance_source": snapshot["source"],
                    "profile_grade": profile_grade,
                    "attendance": attendance,
                    "weekly_study_hours": per_subject_weekly_hours,
                    "subject_difficulty": difficulty,
                    "days_until_exam": days_until_exam,
                    "days_since_last_studied": days_since_last_studied,
                    "risk_score": risk_score,
                    "risk_pct": risk_pct,
                    "feature_order": [
                        "previous_grade_from_assessment",
                        "attendance",
                        "difficulty",
                        "weekly_study_hours",
                        "days_until_exam",
                        "days_since_last_studied",
                        "completion_rate",
                    ],
                    "features": features,
                }

                pred_record = Prediction(
                    user_id=current_user.id,
                    attendance_pct=attendance,
                    assignment_completion_pct=performance_score,
                    weekly_study_hours=per_subject_weekly_hours,
                    total_logged_study_hours=per_subject_weekly_hours,
                    study_days_last_240=0,
                    subject_difficulty=difficulty,
                    avg_exam_score_pct=performance_score,
                    midterm_score_pct=performance_score,
                    final_score_pct=performance_score,
                    assignment_avg_pct=performance_score,
                    year_of_study=profile.year_of_study if profile else 1,
                    cumulative_gpa=profile_grade,
                    predicted_risk_level=risk_level,
                    predicted_grade=predicted_grade,
                    level_of_study=profile.study_level if profile else None,
                    raw_inputs=json.dumps(raw_inputs),
                )
                db.session.add(pred_record)
                batch_results.append({
                    "subject": subject.name,
                    "risk_level": risk_level.title(),
                    "risk_pct": risk_pct,
                    "performance_score": round(performance_score, 1),
                    "performance_source": snapshot["source_label"],
                    "confidence": confidence,
                })
                session_subjects.append(subject.name)
                session_marks.append(round(performance_score))

            if not batch_results:
                db.session.rollback()
                flash("No selected subjects had real Assessment or marksheet scores. Run Assessment or upload a marksheet first.", "warning")
                return render_predict(
                    selected_subject_ids=selected_ids,
                    skipped_subjects=skipped_subjects,
                )

            db.session.commit()
            session["last_prediction"] = highest_result
            session["last_subjects"] = session_subjects
            session["last_marks"] = session_marks
            session["last_study_hours"] = per_subject_weekly_hours / 7.0

            flash(f"Generated {len(batch_results)} subject risk prediction(s).", "success")
            return render_predict(
                prediction_result=highest_result,
                model_used="Random Forest Classifier (random_forest.pkl)",
                batch_results=batch_results,
                skipped_subjects=skipped_subjects,
                selected_subject_ids=selected_ids,
                is_post=True,
            )
        except Exception as e:
            db.session.rollback()
            flash(f"Prediction error: {str(e)}", "danger")
            return render_predict()

    return render_predict()


@student_bp.route("/predict-legacy-disabled", methods=["GET", "POST"])
@login_required
def predict_legacy_disabled():
    return redirect(url_for("student.predict"))

def derive_features_from_marks(subjects, marks):
    """Convert extracted marksheet data into ML model input features."""
    avg_mark = sum(marks) / len(marks) if marks else 50
    lowest_mark = min(marks) if marks else 40
    highest_mark = max(marks) if marks else 80

    return {
        "previous_score": round(avg_mark, 1),       # Feature: avg mark
        "weak_subject_score": round(lowest_mark, 1), # Feature: worst subject
    }


def parse_marksheet(text):
    """
    Extracts subject names and marks from raw OCR text.
    Handles common Nepali marksheet formats (NEB, TU, Pokhara University).
    Returns two parallel lists: subjects[], marks[]
    """
    subjects = []
    marks = []

    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Pattern 1: "Mathematics  75" or "English Language  68/100"
        match = re.search(
            r'([A-Za-z][A-Za-z\s\(\)]{3,40})\s+(\d{1,3})(?:\s*/\s*\d{1,3})?',
            line
        )
        if match:
            subject = match.group(1).strip()
            mark = int(match.group(2))

            # Filter noise — skip lines that look like headers/dates
            skip_keywords = ['date', 'roll', 'name', 'school', 'board',
                             'college', 'total', 'grand', 'serial', 'reg']
            if any(kw in subject.lower() for kw in skip_keywords):
                continue

            # Only accept realistic marks (0–100)
            if 0 <= mark <= 100:
                subjects.append(subject)
                marks.append(mark)

    return subjects, marks


def get_active_subject_match(user_id, detected_name):
    """Return the closest active profile subject plus a 0-1 confidence score."""
    detected = (detected_name or "").strip()
    if not detected:
        return None, 0.0

    profile = StudentProfile.query.filter_by(user_id=user_id).first()
    active = get_profile_subjects(profile)
    if not active:
        return None, 0.0

    detected_key = normalize_subject_name(detected)
    best_subject = None
    best_score = 0.0
    for subject in active:
        subject_key = normalize_subject_name(subject.name)
        if detected_key == subject_key:
            return subject, 1.0
        if detected_key in subject_key or subject_key in detected_key:
            score = 0.9
        else:
            score = SequenceMatcher(None, detected_key, subject_key).ratio()
        if score > best_score:
            best_subject = subject
            best_score = score
    return best_subject, best_score


def map_to_active_subject_name(user_id, detected_name):
    subject, confidence = get_active_subject_match(user_id, detected_name)
    return subject.name if subject and confidence >= 0.62 else detected_name


@student_bp.route("/ocr-extract", methods=["POST"])
@login_required
def ocr_extract():
    if 'marksheet' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
        
    file = request.files['marksheet']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
        
    filename = secure_filename(file.filename)
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    if ext not in ['pdf', 'jpg', 'jpeg', 'png']:
        return jsonify({"error": "Invalid file type. Only PDF and Images allowed."}), 400
        
    try:
        upload_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), '../../app/static/uploads', str(current_user.id))
        os.makedirs(upload_dir, exist_ok=True)
        unique_filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"
        filepath = os.path.join(upload_dir, unique_filename)
        file.save(filepath)
        
        file_type = 'pdf' if ext == 'pdf' else 'image'
        processor = MarksheetProcessor()
        marks_data, confidence = processor.process_file(filepath, file_type)

        profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
        active_subjects = get_profile_subjects(profile)
        subject_options = [{"id": s.id, "name": s.name} for s in active_subjects]
        candidates = []
        for idx, m in enumerate(marks_data):
            pct = processor.convert_to_percentage(m['value'], m['full_marks'])
            if pct is None:
                continue
            matched_subject, match_confidence = get_active_subject_match(current_user.id, m['subject'])
            candidates.append({
                "index": idx,
                "original_subject": m["subject"],
                "matched_subject_id": matched_subject.id if matched_subject and match_confidence >= 0.62 else None,
                "matched_subject_name": matched_subject.name if matched_subject and match_confidence >= 0.62 else "",
                "extracted_value": str(m["value"]),
                "full_marks": str(m["full_marks"]),
                "percentage": pct,
                "row_confidence": float(m.get("confidence", confidence)),
                "match_confidence": round(float(match_confidence), 2),
                "raw_row": m.get("raw_row", ""),
            })

        session["pending_ocr_upload"] = {
            "filename": filename,
            "filepath": filepath,
            "file_type": ext,
            "confidence": confidence,
            "candidates": candidates,
        }

        # Bug 3: Compute low-confidence warning flag
        # Trigger when median match_confidence across all rows is below 0.50
        if candidates:
            sorted_confs = sorted(c["match_confidence"] for c in candidates)
            n = len(sorted_confs)
            median_conf = sorted_confs[n // 2] if n % 2 else (sorted_confs[n // 2 - 1] + sorted_confs[n // 2]) / 2
            low_confidence_warning = median_conf < 0.50
        else:
            low_confidence_warning = False

        return jsonify({
            "status": "preview",
            "candidates": candidates,
            "subject_options": subject_options,
            "overall_confidence": confidence,
            "low_confidence_warning": low_confidence_warning,
        })
        
    except Exception as e:
        return jsonify({
            "error": "OCR extraction failed. Please try a clearer marksheet image or PDF.",
            "details": str(e),
            "candidates": [],
        }), 200


@student_bp.route("/ocr-confirm", methods=["POST"])
@login_required
def ocr_confirm():
    pending = session.get("pending_ocr_upload")
    if not pending:
        return jsonify({"status": "error", "message": "No pending OCR upload to save."}), 400

    data = request.get_json(silent=True) or {}
    rows = data.get("rows", [])
    if not rows:
        return jsonify({"status": "error", "message": "No verified marks were submitted."}), 400

    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    active_ids = {subject.id for subject in get_profile_subjects(profile)}
    candidate_by_index = {
        int(c["index"]): c for c in pending.get("candidates", [])
    }

    doc = AcademicDocument(
        student_id=current_user.id,
        document_type="marksheet",
        document_name=pending.get("filename"),
        file_path=pending.get("filepath"),
        file_type=pending.get("file_type"),
        institution_name="OCR Upload",
        exam_year=local_now_for_user(current_user.id).year,
        extraction_confidence=float(pending.get("confidence") or 0.0),
        processed_at=datetime.utcnow(),
        is_verified=True,
    )
    db.session.add(doc)
    db.session.flush()

    saved = []
    total_pct = 0.0
    for row in rows:
        try:
            candidate = candidate_by_index[int(row.get("index"))]
            subject_id = int(row.get("subject_id"))
            percentage = float(row.get("percentage"))
        except (TypeError, ValueError, KeyError):
            continue
        if subject_id not in active_ids or percentage < 0 or percentage > 100:
            continue
        subject = Subject.query.get(subject_id)
        if not subject:
            continue
        value = str(row.get("value") or candidate.get("extracted_value") or "")
        full_marks = str(row.get("full_marks") or candidate.get("full_marks") or "100")
        try:
            marks_obtained = float(value)
        except ValueError:
            marks_obtained = 0.0
        try:
            full_marks_num = float(full_marks)
        except ValueError:
            full_marks_num = 100.0
        em = ExtractedMark(
            document_id=doc.id,
            subject_name_original=candidate.get("original_subject"),
            subject_name_mapped=subject.name,
            marks_obtained=marks_obtained,
            full_marks=full_marks_num,
            percentage=round(percentage, 2),
            grade="" if value.replace('.', '', 1).isdigit() else value,
        )
        db.session.add(em)
        saved.append({"subject": subject.name, "percentage": round(percentage, 2)})
        total_pct += percentage

    if not saved:
        db.session.rollback()
        return jsonify({"status": "error", "message": "No valid verified subject rows were saved."}), 400

    doc.overall_percentage = round(total_pct / len(saved), 2)
    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    if profile:
        profile.documents_uploaded = (profile.documents_uploaded or 0) + 1
        profile.prior_academic_score = doc.overall_percentage
    db.session.commit()
    session.pop("pending_ocr_upload", None)

    return jsonify({
        "status": "success",
        "message": f"Saved {len(saved)} verified marksheet score(s).",
        "saved": saved,
        "overall_percentage": doc.overall_percentage,
    })


@student_bp.route("/api/subject-performance/<int:subject_id>", methods=["GET"])
@login_required
def get_subject_performance(subject_id):
    is_active = StudentSubject.query.filter_by(
        user_id=current_user.id,
        subject_id=subject_id
    ).first()
    if not is_active:
        return jsonify({"status": "error", "message": "Subject is not active for this student."}), 403

    snapshot = get_subject_performance_snapshot(current_user.id, subject_id)
    return jsonify({
        "status": "success",
        "performance_score": snapshot["score"],
        "source": snapshot["source"],
        "source_label": snapshot["source_label"],
        "has_real_score": snapshot["source"] != "missing",
    })


@student_bp.route("/generate-planner", methods=["POST"])
@login_required
def generate_planner():
    subjects     = request.form.getlist('subjects[]')       # list of selected subjects
    marks        = request.form.getlist('marks[]')          # parallel marks list
    free_slots   = request.form.get('free_slots_json')      # JSON of {day-hour: 'free'} grid
    latest_rows = []
    if not subjects:
        latest_rows = latest_prediction_rows(current_user.id)
        subjects = [row["subject_name"] for row in latest_rows]
        marks = [str(round(row["performance_score"])) for row in latest_rows]
    
    try:
        session_min  = int(request.form.get('session_length', 60))
    except ValueError:
        session_min = 60
        
    try:
        break_min    = int(request.form.get('break_length', 10))
    except ValueError:
        break_min = 10
        
    plan_dur     = request.form.get('plan_duration', '2 weeks')
    strategy     = request.form.get('priority_strategy', 'Weakest subjects first')
    revision_day = request.form.get('revision_day', 'Saturday')
    prediction   = session.get('last_prediction', 'At Risk')
    if latest_rows:
        risk_rank = {"low": 0, "medium": 1, "high": 2}
        worst = max(latest_rows, key=lambda row: risk_rank.get(row["risk_level"], 1), default=None)
        if worst:
            prediction = worst["prediction_result"]

    # Parse JSON free slots and calculate daily average
    free_hours_per_day = 6.0
    if free_slots:
        try:
            free_slots_dict = json.loads(free_slots)
            free_hours_per_day = len([v for v in free_slots_dict.values() if v == 'free']) / 7.0
            if free_hours_per_day == 0:
                free_hours_per_day = 6.0
        except Exception:
            pass

    planner_data = generate_study_planner(
        prediction_result=prediction,
        subjects=subjects,
        marks=[int(m) if m.isdigit() else 50 for m in marks],
        study_hours_per_day=free_hours_per_day,
        session_length=session_min,
        strategy=strategy,
        revision_day=revision_day,
        free_slots_json=free_slots
    )

    # Build subject_ids for click-through study room linkage — read from context
    ctx = get_learning_context(current_user.id)
    subject_ids = {}
    if ctx.profile:
        db_subjects = Subject.query.filter_by(
            level_of_study=ctx.profile.level_of_study,
            program=ctx.profile.program
        ).all()
        for s in db_subjects:
            subject_ids[s.name] = s.id
            subject_ids[s.name.lower()] = s.id
            subject_ids[s.code] = s.id

    for name in subjects:
        if name not in subject_ids and name.lower() not in subject_ids:
            s_match = Subject.query.filter(Subject.name.ilike(name)).first()
            if s_match:
                subject_ids[name] = s_match.id
                subject_ids[name.lower()] = s_match.id

    # ── Context: persist the plan — invalidates cached plan reference
    ctx.update_study_planner(planner_data)

    log_analysis = StudyLogAnalysis.query.filter_by(user_id=current_user.id).first()
    return render_template('student/planner.html', planner=planner_data, subject_ids=subject_ids, log_analysis=log_analysis)


@student_bp.route("/planner/log-hours", methods=["POST"])
@login_required
def planner_log_hours():
    subject_name = request.form.get("subject")
    try:
        hours = float(request.form.get("hours", 1.0))
    except ValueError:
        hours = 1.0

    # ── Context: log study hours — invalidates study_hours, streak, recent_activity caches
    ctx = get_learning_context(current_user.id)
    ctx.log_study_hours(subject_name, hours)

    return jsonify({"status": "success", "message": f"Logged {hours} hours of study for {subject_name}!"})


@student_bp.route("/study/<int:subject_id>", methods=["GET", "POST"])
@login_required
def study_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)

    # ── Context: shared learning state ───────────────────────────────────────
    ctx = get_learning_context(current_user.id)

    # Retrieve all chapters for this subject
    chapters = Chapter.query.filter_by(subject_id=subject.id).order_by(Chapter.chapter_number).all()

    # Fetch user progress for topics of this subject — read from context
    completed_topic_ids = ctx.completed_topic_ids

    # Fetch existing notes for this subject
    user_notes = StudentNote.query.filter_by(user_id=current_user.id, subject_id=subject.id).first()
    notes_content = user_notes.notes_content if user_notes else ""

    # Retrieve flashcards
    flashcards = Flashcard.query.filter_by(subject_id=subject.id).all()

    return render_template(
        "student/study.html",
        subject=subject,
        chapters=chapters,
        completed_topic_ids=completed_topic_ids,
        notes_content=notes_content,
        flashcards=flashcards,
        profile=ctx.profile,
    )


@student_bp.route("/study/api/topic/<int:topic_id>", methods=["GET"])
@login_required
def get_topic_material(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    material = LearningMaterial.query.filter_by(topic_id=topic.id).first()
    
    if not material:
        return jsonify({"status": "not_found", "message": "No learning materials found for this topic."})
        
    flashcards = Flashcard.query.filter_by(chapter_id=topic.chapter_id).all()
    flashcards_list = [{"front": f.front, "back": f.back} for f in flashcards]
    
    bookmark = BookmarkedChapter.query.filter_by(student_id=current_user.id, topic_id=topic_id).first()
    progress = ReviewedChapter.query.filter_by(student_id=current_user.id, topic_id=topic_id).first()
    note = ChapterNote.query.filter_by(student_id=current_user.id, topic_id=topic_id).first()
    p_questions = PastQuestion.query.filter_by(topic_id=topic_id).all()
    past_questions_list = [{"question_text": pq.question_text, "exam_year": pq.exam_year} for pq in p_questions]

    return jsonify({
        "bookmarked": bookmark is not None,
        "progress_status": progress.status if progress else "not started",
        "notes_content": note.content if note else "",
        "past_questions": past_questions_list,
        "status": "success",
        "material": {
            "title": material.title,
            "learning_objectives": material.learning_objectives,
            "introduction": material.introduction,
            "detailed_explanation": material.detailed_explanation,
            "important_definitions": material.important_definitions,
            "concepts": material.concepts,
            "examples": material.examples,
            "worked_examples": material.worked_examples,
            "real_life_applications": material.real_life_applications,
            "diagrams": material.diagrams,
            "key_points": material.key_points,
            "important_facts": material.important_facts,
            "formulae": material.formulae,
            "common_mistakes": material.common_mistakes,
            "mcqs_json": material.mcqs_json,
            "short_questions_json": material.short_questions_json,
            "long_questions_json": material.long_questions_json,
            "critical_thinking_questions_json": material.critical_thinking_questions_json,
            "summary": material.summary,
            "revision_notes": material.revision_notes,
            "estimated_reading_time": material.estimated_reading_time,
            "difficulty_level": material.difficulty_level,
            "learning_outcomes": material.learning_outcomes
        },
        "flashcards": flashcards_list
    })


@student_bp.route("/study/api/topic/<int:topic_id>/generate-ai", methods=["POST"])
@login_required
def generate_ai_topic_material(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    material = LearningMaterial.query.filter_by(topic_id=topic.id).first()
    
    if not material:
        try:
            material = ai_service.generate_lesson_material(topic_id)
        except Exception as e:
            return jsonify({"status": "error", "message": f"Failed to generate lesson: {str(e)}"}), 500
            
    if not material:
        return jsonify({"status": "error", "message": "Failed to create lesson material record."}), 500
        
    flashcards = Flashcard.query.filter_by(chapter_id=topic.chapter_id).all()
    flashcards_list = [{"front": f.front, "back": f.back} for f in flashcards]
    
    bookmark = BookmarkedChapter.query.filter_by(student_id=current_user.id, topic_id=topic_id).first()
    progress = ReviewedChapter.query.filter_by(student_id=current_user.id, topic_id=topic_id).first()
    note = ChapterNote.query.filter_by(student_id=current_user.id, topic_id=topic_id).first()
    p_questions = PastQuestion.query.filter_by(topic_id=topic_id).all()
    past_questions_list = [{"question_text": pq.question_text, "exam_year": pq.exam_year} for pq in p_questions]

    return jsonify({
        "bookmarked": bookmark is not None,
        "progress_status": progress.status if progress else "not started",
        "notes_content": note.content if note else "",
        "past_questions": past_questions_list,
        "status": "success",
        "material": {
            "title": material.title,
            "learning_objectives": material.learning_objectives,
            "introduction": material.introduction,
            "detailed_explanation": material.detailed_explanation,
            "important_definitions": material.important_definitions,
            "concepts": material.concepts,
            "examples": material.examples,
            "worked_examples": material.worked_examples,
            "real_life_applications": material.real_life_applications,
            "diagrams": material.diagrams,
            "key_points": material.key_points,
            "important_facts": material.important_facts,
            "formulae": material.formulae,
            "common_mistakes": material.common_mistakes,
            "mcqs_json": material.mcqs_json,
            "short_questions_json": material.short_questions_json,
            "long_questions_json": material.long_questions_json,
            "critical_thinking_questions_json": material.critical_thinking_questions_json,
            "summary": material.summary,
            "revision_notes": material.revision_notes,
            "estimated_reading_time": material.estimated_reading_time,
            "difficulty_level": material.difficulty_level,
            "learning_outcomes": material.learning_outcomes
        },
        "flashcards": flashcards_list
    })


@student_bp.route("/study/save-notes", methods=["POST"])
@login_required
def study_save_notes():
    subject_id = int(request.form.get("subject_id"))
    content = request.form.get("notes_content", "")
    
    note = StudentNote.query.filter_by(user_id=current_user.id, subject_id=subject_id).first()
    if not note:
        note = StudentNote(user_id=current_user.id, subject_id=subject_id, notes_content=content)
        db.session.add(note)
    else:
        note.notes_content = content
        note.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"status": "success", "message": "Notes saved successfully!"})


@student_bp.route("/study/toggle-topic", methods=["POST"])
@login_required
def study_toggle_topic():
    topic_id = int(request.form.get("topic_id"))
    completed = request.form.get("completed") == "true"

    # ── Context: toggle lesson completion — invalidates progress + achievement caches
    ctx = get_learning_context(current_user.id)
    progress = ctx.toggle_topic_completed(topic_id, completed)

    return jsonify({"status": "success", "completed": progress.is_completed})


@student_bp.route("/study/submit-quiz", methods=["POST"])
@login_required
def study_submit_quiz():
    topic_id = int(request.form.get("topic_id"))
    material = LearningMaterial.query.filter_by(topic_id=topic_id).first()
    if not material or not material.mcqs_json:
        return jsonify({"status": "error", "message": "No quiz found for this topic."}), 404

    mcqs = json.loads(material.mcqs_json)
    user_answers = request.form.getlist("answers[]")

    correct_count = 0
    total = len(mcqs)
    results = []

    for idx, q in enumerate(mcqs):
        user_ans = user_answers[idx] if idx < len(user_answers) else ""
        correct = (user_ans == q["ans"])
        if correct:
            correct_count += 1
        results.append({
            "question": q["q"],
            "options": {"A": q["a"], "B": q["b"], "C": q["c"], "D": q["d"]},
            "correct_ans": q["ans"],
            "user_ans": user_ans,
            "is_correct": correct,
            "explanation": q.get("exp", "No explanation available.")
        })

    topic = Topic.query.get(topic_id)
    chapter = Chapter.query.get(topic.chapter_id)
    score_pct = (correct_count / total) * 100.0 if total > 0 else 0

    # ── Context: save quiz score — invalidates quiz + strong/weak subject caches
    ctx = get_learning_context(current_user.id)
    ctx.save_quiz_score(chapter.subject_id, score_pct, total)

    return jsonify({
        "status": "success",
        "score_pct": score_pct,
        "correct_count": correct_count,
        "total": total,
        "results": results,
    })


@student_bp.route("/planner/adapt-regenerate", methods=["POST"])
@login_required
def planner_adapt_regenerate():
    from app.utils.log_analyzer import analyze_student_logs
    
    # 1. Run analysis
    analysis = analyze_student_logs(current_user.id)
    
    # Get last plan
    last_plan = StudyPlan.query.filter_by(student_id=current_user.id).order_by(StudyPlan.generated_at.desc()).first()
    
    if not last_plan or not last_plan.plan_data:
        flash("No active study plan found to adapt. Generate a plan first.", "warning")
        return redirect(url_for('student.dashboard'))
        
    try:
        plan_dict = json.loads(last_plan.plan_data)
        subjects = [sp["subject"] for sp in plan_dict.get("subject_priorities", [])]
        marks = [sp["mark"] for sp in plan_dict.get("subject_priorities", [])]
        
        # Adapt study hours
        original_daily_hours = plan_dict.get("recommended_daily_hours", 4.0)
        
        if analysis.diverges_significantly:
            adapted_daily_hours = max(2.0, round(original_daily_hours * 0.8, 1))
            msg = f"Logged hours diverged from original targets. Daily study hours adapted down from {original_daily_hours}h to {adapted_daily_hours}h to optimize study load and avoid fatigue."
        else:
            adapted_daily_hours = original_daily_hours
            msg = "Study plan updated to align with log performance."
            
        planner_data = generate_study_planner(
            prediction_result=session.get('last_prediction', 'At Risk'),
            subjects=subjects,
            marks=marks,
            study_hours_per_day=adapted_daily_hours,
            session_length=plan_dict.get("session_length", 60),
            strategy=plan_dict.get("priority_strategy", "Weakest subjects first"),
            revision_day=plan_dict.get("revision_day", "Saturday"),
            free_slots_json=plan_dict.get("free_slots_json")
        )
        
        planner_data["planner_message"] = msg
        
        # Save adapted plan
        new_plan = StudyPlan(
            student_id=current_user.id,
            plan_data=json.dumps(planner_data),
            generated_at=datetime.utcnow()
        )
        db.session.add(new_plan)
        db.session.commit()
        
        # Build subject IDs map
        subject_ids = {}
        profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
        if profile:
            lvl = profile.level_of_study
            db_lvl = lvl
            if lvl == "Class 10":
                db_lvl = "Class 10 (Secondary Education Examination - SEE)"
            elif lvl == "Class 12":
                db_lvl = "Class 12 (National Examination Board - NEB)"
            db_subjects = Subject.query.filter_by(
                level_of_study=db_lvl,
                program=profile.program
            ).all()
            for s in db_subjects:
                subject_ids[s.name] = s.id
                subject_ids[s.name.lower()] = s.id
                subject_ids[s.code] = s.id

        flash("Weekly planner adapted and regenerated successfully!", "success")
        log_analysis = StudyLogAnalysis.query.filter_by(user_id=current_user.id).first()
        return render_template('student/planner.html', planner=planner_data, subject_ids=subject_ids, log_analysis=log_analysis)
    except Exception as e:
        flash(f"Error adapting planner: {str(e)}", "danger")
        return redirect(url_for('student.dashboard'))


@student_bp.route("/api/availability", methods=["GET"])
@login_required
def get_availability():
    slots = AvailabilitySlot.query.filter_by(user_id=current_user.id).all()
    slots_list = [{
        "id": s.id,
        "day_of_week": s.day_of_week,
        "start_time": s.start_time,
        "end_time": s.end_time,
        "slot_type": s.slot_type,
        "category": s.category or s.slot_type,  # fallback to slot_type for old rows
        "custom_label": s.custom_label or "",
        "is_overnight": bool(s.is_overnight)
    } for s in slots]
    return jsonify({"status": "success", "slots": slots_list})


# Valid 7 categories the user can assign
VALID_CATEGORIES = {"Sleep", "Class/Academic", "Sports", "Social/Hangout",
                    "Entertainment", "Personal/Chores", "Other"}


DAY_NAME_TO_SCHEDULE_IDX = {
    'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
    'Friday': 4, 'Saturday': 5, 'Sunday': 6
}


def _slot_minutes(start_time, end_time):
    sh, sm = [int(part) for part in start_time.split(":")]
    eh, em = [int(part) for part in end_time.split(":")]
    return sh * 60 + sm, eh * 60 + em


def _minutes_to_time_str(total_minutes):
    total_minutes = total_minutes % 1440
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def _hour_range_for_slot(start_time, end_time):
    start_mins, end_mins = _slot_minutes(start_time, end_time)
    return _hour_range_for_minutes(start_mins, end_mins)


def _hour_range_for_minutes(start_mins, end_mins):
    start_day_offset = start_mins // 1440
    end_day_offset = end_mins // 1440
    start_mins = start_mins % 1440
    end_mins = end_mins % 1440
    start_hour = start_mins // 60
    end_hour = end_mins // 60
    end_minute = end_mins % 60
    if start_day_offset == end_day_offset and start_mins < end_mins:
        final_hour = end_hour if end_minute > 0 else end_hour - 1
        return [(start_day_offset, h) for h in range(start_hour, final_hour + 1) if 0 <= h < 24]
    final_hour = end_hour if end_minute > 0 else end_hour - 1
    ranges = [(start_day_offset, h) for h in range(start_hour, 24)]
    ranges.extend((end_day_offset, h) for h in range(0, final_hour + 1) if 0 <= h < 24)
    return ranges


def get_available_study_hours_by_day(user_id):
    """
    Single source of truth for schedulable study hours.
    Availability is every hour not covered by Sleep/Class/etc commitments.
    """
    blocked = {i: set() for i in range(7)}
    profile = StudentProfile.query.filter_by(user_id=user_id).first()
    commute_buffer = int(getattr(profile, "commute_buffer_minutes", 0) or 0)
    slots = AvailabilitySlot.query.filter_by(user_id=user_id).all()
    for slot in slots:
        day_idx = DAY_NAME_TO_SCHEDULE_IDX.get(slot.day_of_week)
        if day_idx is None:
            continue
        category = slot.category or slot.slot_type or "Other"
        if category == "Study":
            # Legacy rows mean explicit free time; ignore them because free time is now inverse-derived.
            continue
        try:
            start_time = slot.start_time
            end_time = slot.end_time
            custom_label = (slot.custom_label or "").lower()
            needs_commute = (
                commute_buffer > 0
                and (
                    category == "Class/Academic"
                    or (category == "Other" and any(term in custom_label for term in ("work", "college", "campus", "job")))
                )
            )
            if needs_commute:
                start_mins, end_mins = _slot_minutes(slot.start_time, slot.end_time)
                ranges = _hour_range_for_minutes(start_mins - commute_buffer, end_mins + commute_buffer)
            else:
                ranges = _hour_range_for_slot(start_time, end_time)
            for day_offset, hour in ranges:
                blocked[(day_idx + day_offset) % 7].add(hour)
        except Exception:
            logger.debug("Skipping malformed availability slot %s", getattr(slot, "id", None), exc_info=True)
    return {day: [h for h in range(24) if h not in blocked[day]] for day in range(7)}


def get_available_study_hours_total(user_id):
    return float(sum(len(hours) for hours in get_available_study_hours_by_day(user_id).values()))


@student_bp.route("/api/availability", methods=["POST"])
@login_required
def update_availability():
    data = request.json
    if not isinstance(data, list):
        return jsonify({"status": "error", "message": "Invalid request body: expected a list of slots."}), 400

    try:
        valid_slots = []
        for index, item in enumerate(data):
            day = item.get("day_of_week")
            start = item.get("start_time")
            end = item.get("end_time")
            category = item.get("category") or item.get("slot_type", "")
            custom_label = (item.get("custom_label") or "").strip()[:80]

            if not day or not start or not end or not category:
                return jsonify({"status": "error",
                                "message": f"Slot at index {index} is missing required fields."}), 400

            if not re.match(r"^\d{2}:\d{2}$", start) or not re.match(r"^\d{2}:\d{2}$", end):
                return jsonify({"status": "error",
                                "message": f"Invalid time format in slot at index {index}. Expected HH:MM."}), 400

            # Normalize legacy values from older clients into the seven-category model.
            if category in ("Busy", "Study"):
                category = "Other"
            if category not in VALID_CATEGORIES:
                category = "Other"

            # Map to slot_type for scheduling engine: Sleep stays Sleep, everything else is Busy
            slot_type_value = "Sleep" if category == "Sleep" else "Busy"

            is_over_n = start > end
            valid_slots.append(AvailabilitySlot(
                user_id=current_user.id,
                day_of_week=day,
                start_time=start,
                end_time=end,
                slot_type=slot_type_value,
                category=category,
                custom_label=custom_label if category == "Other" else None,
                is_overnight=is_over_n
            ))

        AvailabilitySlot.query.filter_by(user_id=current_user.id).delete()
        for new_slot in valid_slots:
            db.session.add(new_slot)
        db.session.commit()
        return jsonify({"status": "success",
                        "message": f"Successfully updated {len(valid_slots)} availability slots!"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": f"Failed to update availability: {str(e)}"}), 500


@student_bp.route("/api/availability/summary", methods=["GET"])
@login_required
def availability_summary():
    """Return total weekly hours per category for the dashboard widget."""
    slots = AvailabilitySlot.query.filter_by(user_id=current_user.id).all()
    totals = {}
    for s in slots:
        cat = s.category or s.slot_type or "Other"
        try:
            sh = int(s.start_time.split(":")[0]) * 60 + int(s.start_time.split(":")[1])
            eh = int(s.end_time.split(":")[0]) * 60 + int(s.end_time.split(":")[1])
            dur = ((1440 - sh) + eh) / 60.0 if sh > eh else (eh - sh) / 60.0
        except Exception:
            dur = 0.0
        totals[cat] = round(totals.get(cat, 0.0) + dur, 2)
    return jsonify({"status": "success", "summary": totals})


@student_bp.route("/api/curriculum-data", methods=["GET"])
def get_curriculum_data():
    country = request.args.get("country")
    curriculum = request.args.get("curriculum")
    level = request.args.get("level")
    program = request.args.get("program")
    nepal_levels = ["Class 6", "Class 7", "Class 8", "Class 9", "Class 10", "Class 11", "Class 12", "Bachelors", "Masters"]
    
    if not country:
        countries = [r[0] for r in db.session.query(Subject.country).distinct().all() if r[0]]
        if not countries:
            countries = ["Nepal"]
        return jsonify({"countries": sorted(countries)})
        
    if not curriculum:
        curricula = [r[0] for r in db.session.query(Subject.curriculum).filter_by(country=country).distinct().all() if r[0]]
        if country == "Nepal" and "NEB/CTEVT" not in curricula:
            curricula.append("NEB/CTEVT")
        return jsonify({"curricula": sorted(curricula)})
        
    if not level:
        if country == "Nepal":
            return jsonify({"levels": nepal_levels})
        levels = [r[0] for r in db.session.query(Subject.level_of_study).filter(
            Subject.country == country,
            Subject.curriculum == curriculum
        ).distinct().all() if r[0]]
        return jsonify({"levels": sorted(levels)})
        
    if not program:
        if country == "Nepal":
            if level in ("Class 11", "Class 12"):
                programs = sorted(set(NEPAL_FACULTY_SUBJECT_MAP.keys()) | set(NEPAL_FACULTY_SUBJECT_MAP_C12.keys()))
                return jsonify({"programs": programs})
            if level == "Bachelors":
                return jsonify({"programs": ["BBA", "BCA", "BE Computer", "BE Civil", "BIT", "BSc CSIT", "BSc Nursing", "BTech", "MBBS"]})
            if level == "Masters":
                return jsonify({"programs": ["MBA", "MCA", "MIT", "MSc Computer Science"]})
            return jsonify({"programs": []})
        programs = [r[0] for r in db.session.query(Subject.program).filter(
            Subject.country == country,
            Subject.curriculum == curriculum,
            Subject.level_of_study == level
        ).distinct().all() if r[0]]
        return jsonify({"programs": sorted(programs)})
        
    semesters = [r[0] for r in db.session.query(Subject.semester).filter(
        Subject.country == country,
        Subject.curriculum == curriculum,
        Subject.level_of_study == level,
        Subject.program == program
    ).distinct().all() if r[0]]
    if country == "Nepal" and level == "Bachelors" and not semesters:
        semesters = [f"Semester {i}" for i in range(1, 9)]
    elif country == "Nepal" and level == "Masters" and not semesters:
        semesters = [f"Semester {i}" for i in range(1, 5)]
    return jsonify({"semesters": sorted(semesters)})


@student_bp.route("/subjects", methods=["GET", "POST"])
@login_required
def manage_subjects():
    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        flash("Please complete your profile configuration first", "warning")
        return redirect(url_for("student.dashboard"))
        
    from app.models import StudentSubject
    valid_subjects = get_valid_subjects_for_profile(profile) if profile.study_level else []
    valid_by_id = {s.id: s for s in valid_subjects}
    
    if request.method == "POST":
        selected_ids = []
        seen_subject_names = set()
        for raw_id in request.form.getlist("subjects"):
            try:
                sub_id = int(raw_id)
            except ValueError:
                continue
            subject = valid_by_id.get(sub_id)
            if not subject:
                continue
            key = normalize_subject_name(subject.name)
            if key not in seen_subject_names:
                selected_ids.append(subject.id)
                seen_subject_names.add(key)
        # Clear existing selections
        StudentSubject.query.filter_by(user_id=current_user.id).delete()
        
        # Save new selections
        for sub_id in selected_ids:
            db.session.add(StudentSubject(user_id=current_user.id, subject_id=sub_id))
        db.session.commit()
        flash("Subjects updated successfully!", "success")
        return redirect(url_for("student.manage_subjects"))
        
    # GET method
    selected_subjects = get_profile_subjects(profile)
    selected_ids = [s.id for s in selected_subjects]
    
    if profile.study_level:
        all_valid = valid_subjects or get_valid_subjects_for_profile(profile)
        available_subjects = [s for s in all_valid if s.id not in selected_ids]
    else:
        available_subjects = []
        
    recently_used_ids = [r[0] for r in db.session.query(StudyLog.subject_id).filter_by(user_id=current_user.id).distinct().limit(5).all() if r[0]]
    recently_used = Subject.query.filter(Subject.id.in_(recently_used_ids)).all() if recently_used_ids else []
    
    return render_template(
        "student/subjects.html",
        profile=profile,
        selected_subjects=selected_subjects,
        available_subjects=available_subjects,
        recently_used=recently_used
    )


@student_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    import uuid
    from werkzeug.utils import secure_filename

    # ── Context: shared learning state for this request
    ctx = get_learning_context(current_user.id)

    # Auto-create profile if not present
    if not ctx.profile:
        new_profile = StudentProfile(
            user_id=current_user.id,
            student_number=f"STU-{uuid.uuid4().hex[:8].upper()}",
            cumulative_gpa=0.0,
        )
        db.session.add(new_profile)
        db.session.commit()
        ctx._profile = None  # reset cache so next access picks up new record

    if request.method == "POST":
        current_user.full_name = request.form.get("full_name")

        # Collect profile field updates
        raw_country   = (request.form.get("country") or "Nepal").strip()
        raw_study_lvl = (request.form.get("study_level") or "").strip()
        raw_program   = (request.form.get("program") or "").strip()
        raw_semester  = (request.form.get("semester") or "").strip()
        raw_timezone  = (request.form.get("timezone") or default_timezone_for_country(raw_country)).strip()
        allowed_timezones = set(MULTI_TIMEZONE_OPTIONS.get(raw_country, []))
        if allowed_timezones:
            raw_timezone = raw_timezone if raw_timezone in allowed_timezones else default_timezone_for_country(raw_country)
        else:
            raw_timezone = default_timezone_for_country(raw_country)
        # Derive curriculum automatically from country — never from form input
        derived_curriculum = COUNTRY_CURRICULUM_MAP.get(raw_country, "National")
        # level_of_study mirrors study_level for backward-compat with other parts of the codebase
        profile_data = {
            "country":           raw_country,
            "timezone":          raw_timezone,
            "curriculum":        derived_curriculum,
            "level_of_study":    raw_study_lvl,   # keep in sync for legacy lookups
            "study_level":       raw_study_lvl,
            "program":           raw_program,
            "semester":          raw_semester,
            "cumulative_gpa":    request.form.get("cumulative_gpa", 0.0),
            "commute_buffer_minutes": request.form.get("commute_buffer_minutes", 0),
            "attendance_pct":    float(request.form.get("attendance_pct") or 85.0),
            "explanation_level": request.form.get("explanation_level", "Intermediate"),
            "study_goal":        request.form.get("study_goal", "Improve Grades"),
            "preferred_language":request.form.get("preferred_language", "English"),
        }

        # Handle profile picture (file I/O remains here — not a context concern)
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
                if ext in ['jpg', 'jpeg', 'png']:
                    file.seek(0, os.SEEK_END)
                    file_length = file.tell()
                    file.seek(0)
                    if file_length <= 2 * 1024 * 1024:
                        upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'profile_pics')
                        os.makedirs(upload_dir, exist_ok=True)
                        unique_fn = f"user_{current_user.id}.{ext}"
                        file.save(os.path.join(upload_dir, unique_fn))
                        profile_data["profile_pic"] = f"uploads/profile_pics/{unique_fn}"
                    else:
                        flash("Profile picture exceeds 2MB limit.", "danger")

        # ── Context mutation: update_profile commits all fields + invalidates caches
        ctx.update_profile(profile_data)
        db.session.commit()  # commit full_name change on User model
        flash("Profile updated successfully!", "success")
        return redirect(url_for("student.profile"))

    # GET — read all display data from context (no extra queries)
    return render_template(
        "student/profile.html",
        profile=ctx.profile,
        logged_hours=ctx.study_hours,
        streak=ctx.streak,
        strong_subjects=ctx.strong_subjects,
        weak_subjects=ctx.weak_subjects,
        risk_summary=ctx.risk_summary,
        completed_quizzes_count=ctx.completed_quizzes_count,
        completed_lessons_count=ctx.completed_lessons_count,
        user=current_user,
    )


@student_bp.route("/api/tutor-settings", methods=["POST"])
@login_required
def update_tutor_settings():
    # ── Context mutation: update_learning_preferences commits + invalidates profile cache
    # so next AI assistant request picks up the fresh preferences automatically
    ctx = get_learning_context(current_user.id)
    if not ctx.profile:
        return jsonify({"status": "error", "message": "Profile not found"}), 404

    data = request.json or {}
    ctx.update_learning_preferences(data)
    return jsonify({"status": "success", "message": "Tutor settings updated successfully!"})


# ─── AI ASSISTANT ────────────────────────────────────────────────────────────

@student_bp.route("/assistant", methods=["GET"])
@login_required
def assistant():
    """Render the AI chat assistant page."""
    # ── Context: read profile and history from shared state
    ctx = get_learning_context(current_user.id)

    # Get all active subjects for the subject context selector
    if ctx.profile and ctx.profile.study_level:
        from app.utils.subject_map import SUBJECT_MAP
        level_key = ctx.profile.study_level
        allowed_names = set(SUBJECT_MAP.get(level_key, []))
        subjects = Subject.query.filter(Subject.name.in_(allowed_names)).all() if allowed_names else Subject.query.all()
    else:
        subjects = Subject.query.all()

    # Load existing conversation history from context (session-backed)
    history = ctx.ai_conversation_history

    return render_template(
        "student/assistant.html",
        profile=ctx.profile,
        subjects=subjects,
        history=history,
    )


@student_bp.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    """
    JSON endpoint for the AI chat assistant.
    Reads/writes conversation history through StudentLearningContext.
    Passes enriched context (weak subjects, topics, streak) to the AI.
    """
    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    subject_id = data.get("subject_id")
    if subject_id:
        try:
            subject_id = int(subject_id)
        except (ValueError, TypeError):
            subject_id = None

    if not query:
        return jsonify({"status": "error", "message": "Empty query"}), 400

    # ── Context: read history + enriched profile from shared state
    ctx = get_learning_context(current_user.id)

    # Retrieve history from context (session-backed), keep last 20 messages
    history = ctx.ai_conversation_history[-20:]

    # Build an enriched profile-like object for the AI service.
    # We pass ctx.profile as the profile argument; the enriched system
    # context string is built inside ctx.build_ai_system_context() and
    # injected by calling ai_service with a patched profile wrapper.
    profile = ctx.profile

    try:
        reply = ai_service.chat_with_history(
            history=history,
            user_query=query,
            subject_id=subject_id,
            profile=profile,
        )
    except Exception as e:
        logger.error(f"AI chat error: {e}")
        return jsonify({"status": "error", "message": "The AI tutor is temporarily unavailable. Please try again."}), 503

    # Append new turn to history
    history.append({"role": "user", "content": query})
    history.append({"role": "assistant", "content": reply})

    # ── Context mutation: write history back through context (keeps session in sync)
    ctx.update_ai_history(history)

    return jsonify({"status": "success", "response": reply})


@student_bp.route("/api/chat/clear", methods=["POST"])
@login_required
def clear_chat_history():
    """Clear the AI conversation history through context."""
    ctx = get_learning_context(current_user.id)
    ctx.clear_ai_history()
    return jsonify({"status": "success", "message": "Conversation cleared."})


# ─── FUTURE LEARNING ─────────────────────────────────────────────────────────

@student_bp.route("/future-learning", methods=["GET"])
@login_required
def future_learning():
    """Future Learning page: progression planner, recommended books, career pathways."""
    from app.models import StudentProfile
    from app.utils.subject_map import SUBJECT_MAP
    from app.utils.book_list import (
        BOOK_LIST, CAREER_PATHWAYS, NEXT_LEVEL_MAP, PROGRESSION_PLAN
    )

    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    current_lvl = getattr(profile, "study_level", None) or "University Year 1"

    # ── Next level ────────────────────────────────────────────────────────────
    next_lvl = NEXT_LEVEL_MAP.get(current_lvl)
    next_lvl_subjects = SUBJECT_MAP.get(next_lvl, []) if next_lvl else []

    # ── 4-Week progression plan ───────────────────────────────────────────────
    plan = PROGRESSION_PLAN.get(current_lvl, PROGRESSION_PLAN["default"])

    # ── Recommended books (current + next level combined) ─────────────────────
    # Build subject→books dict for all relevant subjects
    all_subjects = list(SUBJECT_MAP.get(current_lvl, [])) + list(next_lvl_subjects)
    # Deduplicate while preserving order
    seen = set()
    unique_subjects = [s for s in all_subjects if not (s in seen or seen.add(s))]

    books_by_subject = {}
    for subj in unique_subjects:
        b = BOOK_LIST.get(subj, [])
        if b:
            books_by_subject[subj] = b

    # ── Career pathways ───────────────────────────────────────────────────────
    # Try exact match first, then partial match on level prefix
    careers = CAREER_PATHWAYS.get(current_lvl, [])
    if not careers:
        for key in CAREER_PATHWAYS:
            if key.lower() in current_lvl.lower() or current_lvl.lower() in key.lower():
                careers = CAREER_PATHWAYS[key]
                break

    return render_template(
        "student/future_learning.html",
        profile=profile,
        current_lvl=current_lvl,
        next_lvl=next_lvl,
        next_lvl_subjects=next_lvl_subjects,
        plan=plan,
        books_by_subject=books_by_subject,
        careers=careers,
    )


def parse_json_safely(response_text):
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        return json.loads(cleaned)
    except Exception as e:
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        raise e


@student_bp.route("/study-material", methods=["GET"])
@login_required
def study_material():
    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    if not profile or not profile.study_level:
        flash("Please complete your profile configuration first (set your Class Level).", "warning")
        return redirect(url_for("student.profile"))

    from app.models import Subject
    active_subjects = get_profile_subjects(profile)

    if not active_subjects:
        flash("Please configure your Active Subjects first to view study material.", "warning")
        return redirect(url_for("student.manage_subjects"))

    subject_id = request.args.get("subject_id", type=int)
    selected_subject = None
    if subject_id:
        selected_subject = Subject.query.filter(Subject.id == subject_id, Subject.id.in_([s.id for s in active_subjects])).first()

    if not selected_subject:
        session_sub_id = session.get("last_study_material_subject_id")
        if session_sub_id:
            selected_subject = Subject.query.filter(Subject.id == session_sub_id, Subject.id.in_([s.id for s in active_subjects])).first()

    if not selected_subject:
        selected_subject = active_subjects[0]

    session["last_study_material_subject_id"] = selected_subject.id

    saved_material = AIStudyMaterial.query.filter_by(
        user_id=current_user.id,
        subject_id=selected_subject.id,
        class_level=profile.study_level
    ).first()

    material_data = None
    if saved_material:
        try:
            material_data = json.loads(saved_material.content_json)
        except Exception:
            pass

    return render_template(
        "student/study_material.html",
        profile=profile,
        active_subjects=active_subjects,
        selected_subject=selected_subject,
        material=material_data,
        saved_material_obj=saved_material
    )


@student_bp.route("/study-material/generate", methods=["POST"])
@login_required
def generate_study_material_route():
    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    if not profile or not profile.study_level:
        return jsonify({"status": "error", "message": "Please set your class level in Profile first."}), 400

    subject_id = request.form.get("subject_id", type=int)
    if not subject_id:
        return jsonify({"status": "error", "message": "No subject specified."}), 400

    from app.models import StudentSubject, Subject
    is_active = StudentSubject.query.filter_by(user_id=current_user.id, subject_id=subject_id).first()
    if not is_active:
        return jsonify({"status": "error", "message": "Subject is not active for your profile."}), 403

    subject = Subject.query.get(subject_id)
    if not subject:
        return jsonify({"status": "error", "message": "Subject not found."}), 404

    force_regenerate = request.form.get("regenerate", type=int) == 1

    saved_material = AIStudyMaterial.query.filter_by(
        user_id=current_user.id,
        subject_id=subject.id,
        class_level=profile.study_level
    ).first()

    if saved_material and not force_regenerate:
        try:
            return jsonify({
                "status": "success",
                "message": "Loaded from cache.",
                "data": json.loads(saved_material.content_json)
            })
        except Exception:
            pass

    prompt = (
        f"Generate comprehensive and complete study material for Class Level: '{profile.study_level}' "
        f"and Subject Name: '{subject.name}'.\n"
        f"Curriculum context: {profile.curriculum or 'National Curriculum'}.\n"
        f"Language preference: {profile.preferred_language or 'English'}.\n\n"
        "Ensure you cover the syllabus standard for this level. Write the notes in simple, engaging language suitable "
        "for the student's class level. You must provide all 16 items of study material requested in the JSON schema."
    )

    system_instruction = (
        "You are an elite, expert Academic AI Tutor. Generate complete, high-quality study materials for students.\n"
        "You must output the result strictly in valid JSON format. Do not write any preamble, explanation, or markdown "
        "blocks outside the JSON content.\n\n"
        "JSON SCHEMA:\n"
        "{\n"
        '  "introduction": "Detailed introduction text.",\n'
        '  "learning_objectives": ["Objective 1", "Objective 2", "Objective 3", ...],\n'
        '  "detailed_notes": "Detailed notes with HTML formatting (use <p>, <h4>, <ul>, <li>, <strong>, etc.) explaining all major chapters/topics of this curriculum.",\n'
        '  "important_concepts": "Important concepts list or detailed text.",\n'
        '  "easy_explanation": "Simplified explanation using easy-to-understand real-world analogies.",\n'
        '  "real_life_examples": ["Example 1", "Example 2", ...],\n'
        '  "worked_examples": ["Worked Example 1 (e.g. math/science problem, grammar exercises, or historical case studies with step-by-step resolution)", ...],\n'
        '  "important_formulas": "Formulas listing, symbols, and mathematical relationships (or \"Not applicable for this subject\" if not math/science)",\n'
        '  "common_mistakes": ["Mistake 1: explanation", "Mistake 2: explanation", ...],\n'
        '  "key_points": ["Key Point 1", "Key Point 2", ...],\n'
        '  "chapter_summary": "Brief structured summary of the textbook contents.",\n'
        '  "revision_notes": "Handy notes for last-minute exam prep.",\n'
        '  "practice_questions": [\n'
        '     "1. practice question text", "2. practice question text", "3. ...", "4. ...", "5. ...",\n'
        '     "6. ...", "7. ...", "8. ...", "9. ...", "10. practice question text"\n'
        '  ],\n'
        '  "mcqs": [\n'
        "     {\n"
        '       "question": "1. Question text here?",\n'
        '       "options": ["A) Option A", "B) Option B", "C) Option C", "D) Option D"],\n'
        '       "correct_answer": "A",\n'
        '       "explanation": "Why A is correct."\n'
        "     },\n"
        "     ... (exactly 10 objects)\n"
        "  ],\n"
        '  "short_answer_questions": [\n'
        '     "1. Short question text", "2. ...", "3. ...", "4. ...", "5. Short question text"\n'
        '  ],\n'
        '  "flashcards": [\n'
        '     { "front": "Concept/Term/Question", "back": "Definition/Formula/Answer" },\n'
        "     ... (at least 8-10 cards)\n"
        "  ]\n"
        "}"
    )

    try:
        response_text = ai_service.generate_content(prompt, system_instruction=system_instruction)
        material_data = parse_json_safely(response_text)

        if not saved_material:
            saved_material = AIStudyMaterial(
                user_id=current_user.id,
                subject_id=subject.id,
                class_level=profile.study_level,
                content_json=json.dumps(material_data)
            )
            db.session.add(saved_material)
        else:
            saved_material.class_level = profile.study_level
            saved_material.content_json = json.dumps(material_data)
            saved_material.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Generated and saved successfully.",
            "data": material_data
        })
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"AI generation failed: {str(e)}"}), 500


# ── NEW STUDY MATERIAL API IMPROVEMENTS ──────────────────────────────────────

@student_bp.route("/study/api/topic/<int:topic_id>/bookmark", methods=["POST"])
@login_required
def toggle_bookmark(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    bookmark = BookmarkedChapter.query.filter_by(
        student_id=current_user.id, topic_id=topic.id
    ).first()
    if bookmark:
        db.session.delete(bookmark)
        db.session.commit()
        return jsonify({"status": "success", "bookmarked": False, "message": "Bookmark removed."})
    else:
        new_bookmark = BookmarkedChapter(student_id=current_user.id, topic_id=topic.id)
        db.session.add(new_bookmark)
        db.session.commit()
        return jsonify({"status": "success", "bookmarked": True, "message": "Chapter bookmarked."})


@student_bp.route("/study/api/topic/<int:topic_id>/bookmark-status", methods=["GET"])
@login_required
def bookmark_status(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    bookmark = BookmarkedChapter.query.filter_by(
        student_id=current_user.id, topic_id=topic.id
    ).first()
    return jsonify({"status": "success", "bookmarked": bookmark is not None})


@student_bp.route("/study/api/topic/<int:topic_id>/mark-read", methods=["POST"])
@login_required
def mark_read(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    status = request.form.get("status", "completed")
    progress = ReviewedChapter.query.filter_by(
        student_id=current_user.id, topic_id=topic.id
    ).first()
    if not progress:
        progress = ReviewedChapter(
            student_id=current_user.id, topic_id=topic.id, status=status
        )
        db.session.add(progress)
    else:
        progress.status = status
        progress.last_accessed_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"status": "success", "progress_status": progress.status})


@student_bp.route("/study/api/topic/<int:topic_id>/progress", methods=["GET"])
@login_required
def get_progress(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    progress = ReviewedChapter.query.filter_by(
        student_id=current_user.id, topic_id=topic.id
    ).first()
    status = progress.status if progress else "not started"
    return jsonify({"status": "success", "progress_status": status})


@student_bp.route("/study/api/topic/<int:topic_id>/notes", methods=["GET", "POST"])
@login_required
def topic_notes(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    if request.method == "POST":
        content = request.form.get("content", "")
        note = ChapterNote.query.filter_by(
            student_id=current_user.id, topic_id=topic.id
        ).first()
        if not note:
            note = ChapterNote(
                student_id=current_user.id, topic_id=topic.id, content=content
            )
            db.session.add(note)
        else:
            note.content = content
            note.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"status": "success", "message": "Notes saved."})
    else:
        note = ChapterNote.query.filter_by(
            student_id=current_user.id, topic_id=topic.id
        ).first()
        content = note.content if note else ""
        return jsonify({"status": "success", "content": content})


@student_bp.route("/study/api/topic/<int:topic_id>/generate-quiz", methods=["GET"])
@login_required
def generate_chapter_quiz(topic_id):
    import random
    topic = Topic.query.get_or_404(topic_id)
    material = LearningMaterial.query.filter_by(topic_id=topic.id).first()
    content_context = material.detailed_explanation if material else topic.name

    # ── GAP 1: Fetch ALL historically seen question texts for this student+topic ──
    seen_records = TopicSeenQuestion.query.filter_by(
        student_id=current_user.id, topic_id=topic_id
    ).order_by(TopicSeenQuestion.seen_at.desc()).all()
    seen_texts = [r.question_text for r in seen_records]

    exclusion_block = ""
    if seen_texts:
        # Cap at 80 to keep prompt size manageable
        exclusion_sample = seen_texts[:80]
        exclusion_block = (
            "\n\nDo not repeat any of these previously asked questions:\n"
            + "\n".join(f"- {q}" for q in exclusion_sample)
        )

    system_instruction = "You are an expert examiner for the National Examination Board (NEB) of Nepal."

    response_schema = {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "q":   {"type": "STRING", "description": "Question text"},
                "a":   {"type": "STRING"},
                "b":   {"type": "STRING"},
                "c":   {"type": "STRING"},
                "d":   {"type": "STRING"},
                "ans": {"type": "STRING", "description": "Correct option: A, B, C, or D"},
                "exp": {"type": "STRING", "description": "Explanation of why the answer is correct"}
            },
            "required": ["q", "a", "b", "c", "d", "ans", "exp"]
        }
    }

    def build_prompt(num_questions=5):
        return (
            f"Generate exactly {num_questions} unique, distinct multiple-choice questions "
            f"testing deep understanding of the topic '{topic.name}' "
            f"for a student at '{topic.chapter.subject.level_of_study}' level.\n"
            f"Use the following textbook content as context:\n{content_context[:3000]}\n"
            "Each question must have 4 options (A, B, C, D) and one correct answer with a clear explanation."
            f"{exclusion_block}"
        )

    quiz_data = None
    api_error = None

    # ── Attempt 1: Full prompt with structured output ──────────────────────────
    try:
        response_text = ai_service.generate_content(
            build_prompt(5),
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=response_schema
        )
        quiz_data = parse_json_safely(response_text)
        if not isinstance(quiz_data, list) or len(quiz_data) < 1:
            raise ValueError("Empty or invalid response from AI")
    except Exception as e:
        api_error = str(e)
        logger.warning(f"[chapter_quiz] Primary AI attempt failed for topic {topic_id}: {e}")

    # ── Attempt 2: Retry with shorter, simpler prompt (no exclusion list) ─────
    if quiz_data is None:
        try:
            simple_prompt = (
                f"Generate exactly 5 multiple-choice questions on the topic '{topic.name}'. "
                "Each must have options A, B, C, D and one correct answer with explanation."
            )
            response_text = ai_service.generate_content(
                simple_prompt,
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=response_schema
            )
            quiz_data = parse_json_safely(response_text)
            if not isinstance(quiz_data, list) or len(quiz_data) < 1:
                raise ValueError("Empty response on retry")
            logger.info(f"[chapter_quiz] Retry succeeded for topic {topic_id}")
        except Exception as e2:
            api_error = str(e2)
            logger.warning(f"[chapter_quiz] Retry AI attempt also failed for topic {topic_id}: {e2}")

    # ── GAP 2: Rotating fallback pool (4 sets, randomly selected) ─────────────
    if quiz_data is None:
        topic_name = topic.name
        FALLBACK_POOLS = [
            [
                {"q": f"What is the primary objective of studying '{topic_name}'?", "a": "Memorisation only", "b": "Conceptual understanding and application", "c": "Test preparation alone", "d": "None of the above", "ans": "B", "exp": "Education focuses on deep conceptual understanding so students can apply knowledge."},
                {"q": f"Which approach best helps mastery of '{topic_name}'?", "a": "Daily revision with active recall", "b": "Passive reading only", "c": "Skipping difficult sections", "d": "Memorising answers without understanding", "ans": "A", "exp": "Active recall and spaced repetition are proven learning strategies."},
                {"q": f"How does '{topic_name}' relate to other topics in the curriculum?", "a": "It is completely isolated", "b": "It builds foundational skills used across the subject", "c": "It is optional content", "d": "It has no practical relevance", "ans": "B", "exp": "Topics in a curriculum are interconnected; foundational topics support advanced learning."},
                {"q": "Which study technique is most effective for retaining new concepts?", "a": "Cramming one day before exams", "b": "Distributed practice over several days", "c": "Reading once and not revisiting", "d": "Avoiding practice problems", "ans": "B", "exp": "Research shows spaced/distributed practice leads to better long-term retention."},
                {"q": "What role does self-testing play in learning?", "a": "It wastes study time", "b": "It only helps with multiple-choice exams", "c": "It strengthens memory retrieval pathways", "d": "It is less effective than re-reading", "ans": "C", "exp": "Self-testing (retrieval practice) is one of the most effective learning strategies known to science."},
            ],
            [
                {"q": f"Why is conceptual clarity important when learning '{topic_name}'?", "a": "It allows rote memorisation to work faster", "b": "It enables problem-solving across varied question types", "c": "It is less important than memorising examples", "d": "It only matters in theoretical subjects", "ans": "B", "exp": "Conceptual clarity allows transfer of knowledge to new problems."},
                {"q": "What does 'active learning' mean in a study context?", "a": "Attending all classes without taking notes", "b": "Engaging with material through practice, questions and discussion", "c": "Listening passively to lectures", "d": "Highlighting textbook content only", "ans": "B", "exp": "Active learning involves engaging with the content, not passive consumption."},
                {"q": "Which is a sign of strong subject mastery?", "a": "Reciting definitions without error", "b": "Explaining concepts in your own words and solving novel problems", "c": "Scoring high on first attempts only", "d": "Avoiding topics you find difficult", "ans": "B", "exp": "True mastery means being able to explain and apply concepts flexibly."},
                {"q": "How should a student approach topics they find difficult?", "a": "Skip them and focus on easier content", "b": "Ask for help and practise more frequently", "c": "Read them quickly and move on", "d": "Only revisit them the night before exams", "ans": "B", "exp": "Consistent practice and seeking help when stuck are key strategies for improving weak areas."},
                {"q": "What is the benefit of reviewing past mistakes in quizzes?", "a": "It is discouraging and should be avoided", "b": "It confirms what you already know", "c": "It identifies specific knowledge gaps and corrects misconceptions", "d": "It only helps if you scored very poorly", "ans": "C", "exp": "Analysing errors directs future study effort to the areas that need it most."},
            ],
            [
                {"q": f"What makes a question on '{topic_name}' 'hard' difficulty?", "a": "It uses longer sentences", "b": "It requires integrating multiple concepts and deeper analysis", "c": "It has more answer options", "d": "Hard questions are the same as easy, just worded differently", "ans": "B", "exp": "Higher-order questions require synthesis of ideas, not just recall."},
                {"q": "How does feedback after a quiz improve learning?", "a": "It is only useful for the teacher", "b": "It provides no learning benefit", "c": "It helps the student identify and correct misunderstandings immediately", "d": "It only matters if the student fails", "ans": "C", "exp": "Immediate corrective feedback accelerates learning by catching errors early."},
                {"q": "What is the purpose of explanation fields in quiz answers?", "a": "To add extra text to the response", "b": "To help students understand why an answer is correct or incorrect", "c": "To make questions look more complex", "d": "To fill space", "ans": "B", "exp": "Explanations reinforce correct understanding and help learners avoid repeating mistakes."},
                {"q": "Which practice best prepares a student for NEB exams?", "a": "Completing only objective-type questions", "b": "Practising diverse question types including long-answer and application", "c": "Focusing only on model questions from one year", "d": "Memorising mark schemes without understanding", "ans": "B", "exp": "NEB exams include diverse question formats, so varied practice is essential."},
                {"q": "Why should a student track their quiz history?", "a": "For competitive comparison with classmates", "b": "To monitor improvement over time and target weak areas", "c": "It has no practical value", "d": "Only teachers benefit from tracking results", "ans": "B", "exp": "Tracking performance helps personalise study plans and measure genuine improvement."},
            ],
            [
                {"q": f"When you encounter an unfamiliar problem related to '{topic_name}', what should you do first?", "a": "Guess and move on", "b": "Identify which concept or formula applies, then work methodically", "c": "Look up the exact answer without trying", "d": "Skip it entirely", "ans": "B", "exp": "Methodical problem-solving begins with identifying the relevant principle."},
                {"q": "What does spaced repetition help with?", "a": "Learning multiple subjects simultaneously without breaks", "b": "Moving information from short-term to long-term memory", "c": "Avoiding the need to study difficult topics", "d": "Completing homework faster", "ans": "B", "exp": "Spaced repetition leverages the spacing effect to improve long-term retention."},
                {"q": "Why is interleaving different topics during study sessions effective?", "a": "It is not effective; blocked practice is always better", "b": "It forces the brain to distinguish between concepts, improving discrimination", "c": "It reduces the total study time needed", "d": "It only works for mathematics", "ans": "B", "exp": "Interleaving increases difficulty in a productive way, leading to better long-term learning."},
                {"q": "What is the role of prior knowledge when learning a new topic?", "a": "Prior knowledge is irrelevant to new learning", "b": "It can interfere with new concepts and should be ignored", "c": "It provides a framework to connect and organise new information", "d": "Only prior knowledge gained from textbooks counts", "ans": "C", "exp": "Prior knowledge provides cognitive scaffolding, making new information easier to integrate."},
                {"q": "What does it mean to study 'deeply' rather than 'broadly'?", "a": "Covering the maximum number of topics in minimum time", "b": "Focusing on understanding relationships, causes and implications within fewer topics", "c": "Reading every page of every textbook", "d": "Only studying topics likely to appear in exams", "ans": "B", "exp": "Deep study prioritises comprehension and long-term understanding over surface-level coverage."},
            ],
        ]
        quiz_data = random.choice(FALLBACK_POOLS)
        logger.warning(f"[chapter_quiz] Using rotating fallback pool for topic {topic_id}")
        return jsonify({
            "status": "success",
            "quiz": quiz_data,
            "degraded": True,
            "message": "Limited connectivity — showing a standard practice quiz. Personalisation will resume when the AI service is back."
        })

    return jsonify({"status": "success", "quiz": quiz_data, "degraded": False})



@student_bp.route("/study/api/topic/<int:topic_id>/submit-quiz", methods=["POST"])
@login_required
def submit_chapter_quiz(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    score = request.form.get("score", type=float)
    total = request.form.get("total", type=int, default=5)
    if score is None:
        return jsonify({"status": "error", "message": "Missing score."}), 400

    # ── Persist overall score row (same as before) ─────────────────────────────
    quiz_score = ChapterQuizScore(
        student_id=current_user.id, topic_id=topic.id, score=score, total_questions=total
    )
    db.session.add(quiz_score)
    db.session.flush()  # Get quiz_score.id before commit

    # ── GAP 1 + Per-question tracking: parse individual results from client ─────
    # The client sends JSON: questions=[{q, ans, selected, correct: bool}]
    try:
        questions_json = request.form.get("questions", "[]")
        questions_data = json.loads(questions_json)
    except Exception:
        questions_data = []

    if questions_data:
        for item in questions_data:
            q_text = item.get("q", "")
            if not q_text:
                continue

            # Per-question result row
            result_row = ChapterQuizResult(
                quiz_score_id=quiz_score.id,
                student_id=current_user.id,
                topic_id=topic.id,
                question_text=q_text,
                selected_answer=item.get("selected", None),
                correct_answer=item.get("ans", ""),
                was_correct=bool(item.get("correct", False))
            )
            db.session.add(result_row)

            # Permanent seen-question record so future quizzes exclude it
            already_seen = TopicSeenQuestion.query.filter_by(
                student_id=current_user.id,
                topic_id=topic.id,
                question_text=q_text
            ).first()
            if not already_seen:
                seen_row = TopicSeenQuestion(
                    student_id=current_user.id,
                    topic_id=topic.id,
                    question_text=q_text
                )
                db.session.add(seen_row)

    db.session.commit()
    return jsonify({"status": "success", "score": score, "total": total})


@student_bp.route("/study/api/topic/<int:topic_id>/tts", methods=["POST"])
@login_required
def get_tts_audio(topic_id):
    api_key = current_app.config.get("ELEVENLABS_API_KEY")
    if not api_key:
        logger.warning("ELEVENLABS_API_KEY is not configured. Browser client-side SpeechSynthesis is used as fallback.")
        return jsonify({"status": "info", "message": "Local speech synth used. Configuration key missing in server env."})
    return jsonify({"status": "success", "message": "API config detected."})


@student_bp.route("/study/api/topic/<int:topic_id>/pdf", methods=["GET"])
@login_required
def get_chapter_pdf(topic_id):
    import time
    import fitz
    import re
    topic = Topic.query.get_or_404(topic_id)
    material = LearningMaterial.query.filter_by(topic_id=topic.id).first()
    if not material:
        return jsonify({"status": "error", "message": "Material not found. Generate lesson first."}), 404
        
    cache_dir = os.path.join(current_app.root_path, "static", "cache", "pdfs")
    os.makedirs(cache_dir, exist_ok=True)
    pdf_filename = f"chapter_{topic_id}.pdf"
    pdf_path = os.path.join(cache_dir, pdf_filename)
    
    is_first_time = not os.path.exists(pdf_path)
    if is_first_time:
        time.sleep(2)
        
        doc = fitz.open()
        content = f"SUBJECT: {topic.chapter.subject.name}\n"
        content += f"CHAPTER {topic.chapter.chapter_number}: {topic.chapter.name}\n"
        content += f"TOPIC: {topic.name}\n\n"
        
        if material.learning_objectives:
            content += "LEARNING OBJECTIVES:\n"
            content += re.sub('<[^<]+?>', '', material.learning_objectives) + "\n\n"
        if material.introduction:
            content += "INTRODUCTION:\n"
            content += re.sub('<[^<]+?>', '', material.introduction) + "\n\n"
        if material.detailed_explanation:
            content += "DETAILED EXPLANATION:\n"
            content += re.sub('<[^<]+?>', '', material.detailed_explanation) + "\n\n"
        if material.concepts:
            content += "CORE CONCEPTS:\n"
            content += re.sub('<[^<]+?>', '', material.concepts) + "\n\n"
        if material.summary:
            content += "SUMMARY:\n"
            content += re.sub('<[^<]+?>', '', material.summary) + "\n\n"
            
        text = content
        while text:
            page = doc.new_page()
            rect = fitz.Rect(50, 50, 550, 750)
            rc = page.insert_textbox(rect, text, fontsize=10, fontname="helv")
            if rc < 0:
                break
            text = text[rc:]
            
        doc.save(pdf_path)
        doc.close()
        
    progress = ReviewedChapter.query.filter_by(student_id=current_user.id, topic_id=topic.id).first()
    if not progress:
        progress = ReviewedChapter(student_id=current_user.id, topic_id=topic.id, status="in progress")
        db.session.add(progress)
        db.session.commit()

    from flask import send_from_directory
    return send_from_directory(cache_dir, pdf_filename, as_attachment=True)


@student_bp.route("/study-material/search", methods=["GET"])
@login_required
def search_study_materials():
    query = request.args.get("q", "").lower().strip()
    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    active_subjects = get_profile_subjects(profile)
    active_subject_ids = [s.id for s in active_subjects]
    
    results = []
    if query:
        topics = Topic.query.join(Chapter).filter(
            Chapter.subject_id.in_(active_subject_ids),
            (Topic.name.like(f"%{query}%")) | (Chapter.name.like(f"%{query}%"))
        ).all()
        for t in topics:
            results.append({
                "topic_id": t.id,
                "topic_name": t.name,
                "chapter_name": t.chapter.name,
                "subject_name": t.chapter.subject.name,
                "subject_id": t.chapter.subject_id
            })
    return jsonify({"status": "success", "results": results})


@student_bp.route("/my-downloads", methods=["GET"])
@login_required
def my_downloads_page():
    downloads = ReviewedChapter.query.filter(
        ReviewedChapter.student_id == current_user.id,
        ReviewedChapter.status.in_(["completed", "in progress"])
    ).order_by(ReviewedChapter.last_accessed_at.desc()).all()
    
    profile = StudentProfile.query.filter_by(user_id=current_user.id).first()
    
    return render_template(
        "student/my_downloads.html",
        downloads=downloads,
        profile=profile
    )
