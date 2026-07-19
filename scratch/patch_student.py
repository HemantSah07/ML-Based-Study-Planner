content = open('app/routes/student.py', 'rb').read().decode('utf-8')

OLD_BLOCK = (
    '        profile_data = {\r\n'
    '            "country":           raw_country,\r\n'
    '            "timezone":          raw_timezone,\r\n'
    '            "curriculum":        derived_curriculum,\r\n'
    '            "level_of_study":    raw_study_lvl,\r\n'
    '            "study_level":       raw_study_lvl,\r\n'
    '            "program":           raw_program,\r\n'
    '            "semester":          raw_semester,\r\n'
    '            "university":        raw_university,\r\n'
    '            "cumulative_gpa":    request.form.get("cumulative_gpa", 0.0),\r\n'
    '            "commute_buffer_minutes": request.form.get("commute_buffer_minutes", 0),\r\n'
    '            "attendance_pct":    float(request.form.get("attendance_pct") or 85.0),\r\n'
    '            "explanation_level": request.form.get("explanation_level", "Intermediate"),\r\n'
    '            "study_goal":        request.form.get("study_goal", "Improve Grades"),\r\n'
    '            "preferred_language":request.form.get("preferred_language", "English"),\r\n'
    '            "peak_focus_time":   request.form.get("peak_focus_time") or "Morning",\r\n'
    '        }'
)

NEW_BLOCK = (
    '        # Programs with explicit duration selection (frontend PROGRAMS_WITH_DURATION mirrors this).\r\n'
    '        # BSc CSIT excluded intentionally: implicit 4-year TU standard, no duration field shown.\r\n'
    '        DURATION_PROGRAMS = {"BSc IT"}\r\n'
    '        raw_program_duration = request.form.get("program_duration", "").strip() \\\r\n'
    '            if raw_program in DURATION_PROGRAMS else ""\r\n'
    '\r\n'
    '        profile_data = {\r\n'
    '            "country":           raw_country,\r\n'
    '            "timezone":          raw_timezone,\r\n'
    '            "curriculum":        derived_curriculum,\r\n'
    '            "level_of_study":    raw_study_lvl,\r\n'
    '            "study_level":       raw_study_lvl,\r\n'
    '            "program":           raw_program,\r\n'
    '            "program_duration":  raw_program_duration,\r\n'
    '            "semester":          raw_semester,\r\n'
    '            "university":        raw_university,\r\n'
    '            "cumulative_gpa":    request.form.get("cumulative_gpa", 0.0),\r\n'
    '            "commute_buffer_minutes": request.form.get("commute_buffer_minutes", 0),\r\n'
    '            "attendance_pct":    float(request.form.get("attendance_pct") or 85.0),\r\n'
    '            "explanation_level": request.form.get("explanation_level", "Intermediate"),\r\n'
    '            "study_goal":        request.form.get("study_goal", "Improve Grades"),\r\n'
    '            "preferred_language":request.form.get("preferred_language", "English"),\r\n'
    '            "peak_focus_time":   request.form.get("peak_focus_time") or "Morning",\r\n'
    '        }'
)

if OLD_BLOCK in content:
    content = content.replace(OLD_BLOCK, NEW_BLOCK, 1)
    open('app/routes/student.py', 'wb').write(content.encode('utf-8'))
    print('SUCCESS: student.py updated with program_duration')
else:
    print('ERROR: target block not found — check line endings')
    # Debug: show snippet
    idx = content.find('profile_data = {')
    print(repr(content[idx:idx+200]))
