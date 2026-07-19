"""Append Section 2: Content Management routes — replaces stub"""

section2_code = '''

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
    """Content overview stats: subject/chapter/question counts."""
    from app.models import Chapter, AssessmentQuestion
    from sqlalchemy import func
    subjects = SubjectModel.query.order_by(SubjectModel.name).all()
    rows = []
    for s in subjects:
        ch_count = Chapter.query.filter_by(subject_id=s.id).count()
        q_count = AssessmentQuestion.query.filter_by(subject_id=s.id).count()
        rows.append({"subject": s, "chapters": ch_count, "questions": q_count})
    total_questions = AssessmentQuestion.query.count()
    return render_template(
        "admin/content/stats.html",
        rows=rows, total_questions=total_questions,
    )

'''

with open('app/routes/admin.py', 'a', encoding='utf-8') as f:
    f.write(section2_code)

print("SUCCESS: Section 2 routes appended")
