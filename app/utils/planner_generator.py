# Subject-Aware Study Planner Generator
import json

def generate_study_planner(prediction_result, subjects, marks, study_hours_per_day, session_length=60, strategy='Weakest subjects first', revision_day='Saturday', free_slots_json=None):
    """
    Generates a personalized weekly study plan based on:
    - ML prediction result (Pass/At Risk/Fail)
    - Actual subjects and marks from the marksheet
    - Available study hours per day
    - Session length (minutes)
    - Prioritisation strategy (Weakest first vs Balanced)
    - Revision day choice
    - Time availability grid (JSON mapping day-hour)

    Returns: dict with daily schedule, subject priorities, time allocations
    """
    DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    
    # Step 1: Score each subject — lower mark = higher priority
    subject_priorities = []
    for subject, mark in zip(subjects, marks):
        if mark < 40:
            priority = "Critical"
            weight = 3.0 if strategy == "Weakest subjects first" else 1.8
        elif mark < 60:
            priority = "Weak"
            weight = 2.0 if strategy == "Weakest subjects first" else 1.5
        elif mark < 75:
            priority = "Average"
            weight = 1.5 if strategy == "Weakest subjects first" else 1.3
        else:
            priority = "Strong"
            weight = 1.0

        subject_priorities.append({
            "subject": subject,
            "mark": mark,
            "priority": priority,
            "weight": weight
        })

    # Sort: Critical > Weak > Average > Strong
    subject_priorities.sort(key=lambda x: x["weight"], reverse=True)

    # Step 2: Adjust total hours based on prediction result
    if prediction_result == "Fail":
        boost_factor = 1.4   # 40% more study time recommended
    elif prediction_result == "At Risk":
        boost_factor = 1.2
    else:  # Pass
        boost_factor = 1.0

    adjusted_hours = min(study_hours_per_day * boost_factor, 10.0)  # Cap at 10h

    # Step 3: Parse free slots
    free_slots = {}
    if free_slots_json:
        try:
            free_slots = json.loads(free_slots_json)
        except Exception:
            pass

    # Group free slots by day
    # free_slots is mapping "Day-Hour" -> "state" (e.g. "Monday-17" -> "free")
    day_free_hours = {day: [] for day in DAYS}
    for key, status in free_slots.items():
        if status == "free" and "-" in key:
            parts = key.split("-")
            day = parts[0]
            try:
                hour = int(parts[1])
                if day in day_free_hours:
                    day_free_hours[day].append(hour)
            except ValueError:
                pass

    # Sort hours for each day chronologically
    for day in DAYS:
        day_free_hours[day].sort()

    # Step 4: Distribute time across subjects per day
    total_weight = sum(s["weight"] for s in subject_priorities)
    schedule = {day: [] for day in DAYS}

    # Identify revision day
    rev_day_str = revision_day.strip().capitalize()
    if rev_day_str not in DAYS:
        rev_day_str = 'Saturday'

    # Convert session_length to hours
    session_hr = round(session_length / 60.0, 1)

    for day in DAYS:
        hours_list = day_free_hours[day]
        if not hours_list:
            continue
            
        if day == rev_day_str:
            # Revision day: Revision of weakest subjects + mock test
            weak_subjects = [s for s in subject_priorities if s["priority"] in ["Critical", "Weak"]]
            for idx, hour in enumerate(hours_list):
                start_time_str = f"{hour:02d}:00"
                end_time_str = f"{(hour+1)%24:02d}:00"
                
                if weak_subjects and (idx % 2 == 0):
                    subj = weak_subjects[idx % len(weak_subjects)]
                    schedule[day].append({
                        "subject": subj["subject"],
                        "hours": session_hr,
                        "start_time": start_time_str,
                        "end_time": end_time_str,
                        "priority": "Revision",
                        "focus_tip": "Review notes and attempt past exam questions"
                    })
                else:
                    schedule[day].append({
                        "subject": "Mock Test / Self-Assessment",
                        "hours": session_hr,
                        "start_time": start_time_str,
                        "end_time": end_time_str,
                        "priority": "Test",
                        "focus_tip": "Attempt full-length timed practice test"
                    })
        else:
            # Regular study day: distribute based on weights
            subject_pool = []
            for sp in subject_priorities:
                slots_count = max(1, int(round((sp["weight"] / total_weight) * len(hours_list))))
                subject_pool.extend([sp] * slots_count)
            
            # Ensure subject pool is large enough
            if len(subject_pool) < len(hours_list):
                extra = len(hours_list) - len(subject_pool)
                subject_pool.extend(subject_priorities * (extra // len(subject_priorities) + 1))
            
            # Match sizes
            subject_pool = subject_pool[:len(hours_list)]
            
            for hour, sp in zip(hours_list, subject_pool):
                start_time_str = f"{hour:02d}:00"
                end_time_str = f"{(hour+1)%24:02d}:00"
                
                schedule[day].append({
                    "subject": sp["subject"],
                    "hours": session_hr,
                    "start_time": start_time_str,
                    "end_time": end_time_str,
                    "priority": sp["priority"],
                    "focus_tip": get_subject_tip(sp["subject"], sp["priority"])
                })

    # Fallback to general block schedule if no free slots were selected at all
    has_any_slots = any(len(slots) > 0 for slots in schedule.values())
    if not has_any_slots:
        for day in DAYS:
            if day == rev_day_str:
                schedule[day] = [{
                    "subject": "Mock Test / Self-Assessment",
                    "hours": round(adjusted_hours, 1),
                    "priority": "Test",
                    "focus_tip": "Attempt full-length timed practice test"
                }]
            else:
                daily_subjects = []
                for sp in subject_priorities:
                    allocated = round((sp["weight"] / total_weight) * adjusted_hours, 1)
                    if allocated < 0.5:
                        allocated = 0.5
                    daily_subjects.append({
                        "subject": sp["subject"],
                        "hours": allocated,
                        "priority": sp["priority"],
                        "focus_tip": get_subject_tip(sp["subject"], sp["priority"])
                    })
                schedule[day] = daily_subjects

    return {
        "schedule": schedule,
        "subject_priorities": subject_priorities,
        "recommended_daily_hours": round(adjusted_hours, 1),
        "prediction_result": prediction_result,
        "planner_message": get_planner_message(prediction_result),
        "strategy": strategy,
        "revision_day": revision_day
    }


def get_subject_tip(subject, priority):
    """Returns subject-specific (non-generic) study tip based on subject name and priority."""
    subject_lower = subject.lower()

    tips = {
        ("math", "Critical"): "Focus on formula derivations and solve 20 numericals daily",
        ("math", "Weak"): "Practice chapter-wise exercises; prioritize algebra and calculus",
        ("math", "Average"): "Attempt mixed problem sets; time yourself",
        ("math", "Strong"): "Maintain with weekly revision",
        ("english", "Critical"): "Practice grammar daily + read 1 passage for comprehension",
        ("english", "Weak"): "Focus on essay writing structure and vocabulary building",
        ("physics", "Critical"): "Re-read derivations and solve numerical problems from past papers",
        ("physics", "Weak"): "Focus on electromagnetism and optics chapters",
        ("chemistry", "Critical"): "Memorize reactions and practice balancing equations daily",
        ("biology", "Critical"): "Draw labeled diagrams daily; use flashcards for definitions",
        ("computer", "Critical"): "Practice coding problems and review data structure concepts",
        ("nepali", "Critical"): "Write one essay daily; revise grammar rules",
        ("account", "Critical"): "Practice journal entries and ledger posting daily",
        ("economics", "Critical"): "Focus on graphs, definitions, and numerical examples",
    }

    for key_subject, key_priority in tips:
        if key_subject in subject_lower and key_priority == priority:
            return tips[(key_subject, key_priority)]

    # Fallback by priority only
    fallback = {
        "Critical": f"Dedicate maximum time to {subject}; consult teacher immediately",
        "Weak": f"Focus on fundamental concepts in {subject}",
        "Average": f"Practice past exam questions for {subject}",
        "Strong": f"Maintain {subject} with weekly light revision"
    }
    return fallback.get(priority, f"Review {subject} regularly")


def get_planner_message(prediction_result):
    messages = {
        "Pass": "You're on track! This planner will help you maintain and improve your performance.",
        "At Risk": "You need focused effort. Follow this planner strictly to turn things around.",
        "Fail": "Urgent attention needed. Stick to this intensive plan and seek teacher support immediately."
    }
    return messages.get(prediction_result, "Follow this planner to improve your academic performance.")
