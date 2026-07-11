from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.models import User, Prediction, StudyLog
from datetime import datetime, timedelta

admin_bp = Blueprint("admin", __name__)

@admin_bp.before_request
@login_required
def require_admin():
    if current_user.role != 'admin':
        return redirect(url_for('student.dashboard'))

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