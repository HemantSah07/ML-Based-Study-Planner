with open('app/routes/student.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update profile rendering to pass active_universities
old_render = """    return render_template(
        "student/profile.html",
        edit_mode=edit_mode,
        profile=ctx.profile,
        user=current_user,
        logged_hours=ctx.study_hours,
        streak=ctx.streak,
        risk_summary=ctx.risk_summary,
        completed_quizzes_count=ctx.completed_quizzes_count,
        completed_lessons_count=ctx.completed_lessons_count,
        
        # Analytics details
        subject_mastery=mastery,
        weak_topics=weak_topics,
        recent_assessments=summary["recent"],
        overall_stats={
            "total_attempted": summary["total_attempted"],
            "correct": summary["total_correct"],
            "incorrect": summary["total_incorrect"],
            "accuracy": summary["accuracy"]
        },
        strongest_subject=academic["strongest_subject"],
        weakest_subject=academic["weakest_subject"],
        improvement_trend=academic["improvement_trend"],
        overall_mastery=academic["overall_mastery"],
        subjects=ctx.subjects,
    )"""

new_render = """    from app.models import University
    active_unis = University.query.filter_by(is_active=True).order_by(University.sort_order).all()
    return render_template(
        "student/profile.html",
        edit_mode=edit_mode,
        profile=ctx.profile,
        user=current_user,
        logged_hours=ctx.study_hours,
        streak=ctx.streak,
        risk_summary=ctx.risk_summary,
        completed_quizzes_count=ctx.completed_quizzes_count,
        completed_lessons_count=ctx.completed_lessons_count,
        
        # Analytics details
        subject_mastery=mastery,
        weak_topics=weak_topics,
        recent_assessments=summary["recent"],
        overall_stats={
            "total_attempted": summary["total_attempted"],
            "correct": summary["total_correct"],
            "incorrect": summary["total_incorrect"],
            "accuracy": summary["accuracy"]
        },
        strongest_subject=academic["strongest_subject"],
        weakest_subject=academic["weakest_subject"],
        improvement_trend=academic["improvement_trend"],
        overall_mastery=academic["overall_mastery"],
        subjects=ctx.subjects,
        active_universities=active_unis,
    )"""

if old_render.replace('\r\n', '\n') in content.replace('\r\n', '\n'):
    content = content.replace(old_render.replace('\r\n', '\n'), new_render.replace('\r\n', '\n'))
    print("SUCCESS: profile route render modified")
else:
    # Try with raw string line-ending normalization
    content_norm = content.replace('\r\n', '\n')
    old_norm = old_render.replace('\r\n', '\n')
    if old_norm in content_norm:
        content = content_norm.replace(old_norm, new_render.replace('\r\n', '\n')).replace('\n', '\r\n')
        print("SUCCESS: profile route render modified (normalized)")
    else:
        print("ERROR: profile route render NOT modified")

# 2. Update get_curriculum_data API to fetch database-backed taxonomy
old_api = """@student_bp.route("/api/curriculum-data", methods=["GET"])
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
    return jsonify({"semesters": sorted(semesters)})"""

new_api = """@student_bp.route("/api/curriculum-data", methods=["GET"])
def get_curriculum_data():
    from app.models import EducationLevel, Faculty, CurriculumProgram
    country = request.args.get("country")
    curriculum = request.args.get("curriculum")
    level = request.args.get("level")
    program = request.args.get("program")
    nepal_levels = ["Class 6", "Class 7", "Class 8", "Class 9", "Class 10", "Class 11", "Class 12", "Bachelors", "Masters"]
    
    if not country:
        countries = [r[0] for r in db.session.query(Subject.country).distinct().all() if r[0]]
        # also check active universities/levels countries
        for el in EducationLevel.query.filter_by(is_active=True).distinct(EducationLevel.country).all():
            if el.country not in countries:
                countries.append(el.country)
        if not countries:
            countries = ["Nepal"]
        return jsonify({"countries": sorted(list(set(countries)))})
        
    if not curriculum:
        curricula = [r[0] for r in db.session.query(Subject.curriculum).filter_by(country=country).distinct().all() if r[0]]
        if country == "Nepal" and "NEB/CTEVT" not in curricula:
            curricula.append("NEB/CTEVT")
        return jsonify({"curricula": sorted(list(set(curricula)))})
        
    if not level:
        levels_db = EducationLevel.query.filter_by(country=country, is_active=True).order_by(EducationLevel.sort_order.asc()).all()
        if levels_db:
            return jsonify({"levels": [l.name for l in levels_db]})
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
                facs_db = Faculty.query.filter_by(country="Nepal", is_active=True).filter((Faculty.level_name == level) | (Faculty.level_name == None)).order_by(Faculty.sort_order.asc()).all()
                if facs_db:
                    return jsonify({"programs": [f.name for f in facs_db]})
                programs = sorted(set(NEPAL_FACULTY_SUBJECT_MAP.keys()) | set(NEPAL_FACULTY_SUBJECT_MAP_C12.keys()))
                return jsonify({"programs": programs})
            if level == "Bachelors":
                progs_db = CurriculumProgram.query.filter_by(level_name="Bachelors", country="Nepal", is_active=True).order_by(CurriculumProgram.sort_order.asc()).all()
                if progs_db:
                    return jsonify({"programs": [p.name for p in progs_db]})
                return jsonify({"programs": ["BBA", "BCA", "BE Computer", "BE Civil", "BIT", "BSc CSIT", "BSc Nursing", "BTech", "MBBS"]})
            if level == "Masters":
                progs_db = CurriculumProgram.query.filter_by(level_name="Masters", country="Nepal", is_active=True).order_by(CurriculumProgram.sort_order.asc()).all()
                if progs_db:
                    return jsonify({"programs": [p.name for p in progs_db]})
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
    return jsonify({"semesters": sorted(semesters)})"""

if old_api.replace('\r\n', '\n') in content.replace('\r\n', '\n'):
    content = content.replace(old_api.replace('\r\n', '\n'), new_api.replace('\r\n', '\n'))
    print("SUCCESS: api route modified")
else:
    # Try with raw string line-ending normalization
    content_norm = content.replace('\r\n', '\n')
    old_norm = old_api.replace('\r\n', '\n')
    if old_norm in content_norm:
        content = content_norm.replace(old_norm, new_api.replace('\r\n', '\n')).replace('\n', '\r\n')
        print("SUCCESS: api route modified (normalized)")
    else:
        print("ERROR: api route NOT modified")

with open('app/routes/student.py', 'w', encoding='utf-8') as f:
    f.write(content)
