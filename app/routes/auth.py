from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db, bcrypt
from app.models import User, AuditLog, StudentProfile, AvailabilitySlot, University
from app.utils.timezone_utils import default_timezone_for_country
from datetime import datetime, timedelta
import re

auth_bp = Blueprint("auth", __name__)

COUNTRY_CURRICULUM_MAP = {
    "Nepal": "NEB/CTEVT",
    "United States": "US Common Core/AP",
    "United Kingdom": "A-Levels/GCSE",
    "Australia": "HSC/VCE/SACE",
    "Canada": "Provincial/IB",
    "India": "CBSE/ICSE/State Boards",
}

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('student.dashboard'))
        
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        ip = request.remote_addr
        
        # Check lockout
        fifteen_mins_ago = datetime.utcnow() - timedelta(minutes=15)
        failed_attempts = AuditLog.query.filter(
            AuditLog.ip_address == ip,
            AuditLog.status == 'failed',
            AuditLog.timestamp >= fifteen_mins_ago
        ).count()
        
        if failed_attempts >= 5:
            flash("Too many failed attempts. Try again in 15 minutes", "danger")
            return render_template("auth/login.html")
            
        user = User.query.filter_by(email=email).first()
        
        if not user:
            log = AuditLog(ip_address=ip, email_attempted=email, status='failed')
            db.session.add(log)
            db.session.commit()
            flash("No account found with this email address", "danger")
            return render_template("auth/login.html")
            
        if not user.is_active:
            flash("Your account has been deactivated. Contact admin", "danger")
            return render_template("auth/login.html")
            
        if bcrypt.check_password_hash(user.password_hash, password):
            log = AuditLog(ip_address=ip, email_attempted=email, status='success')
            db.session.add(log)
            db.session.commit()
            
            login_user(user)
            flash("Login successful!", "success")
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            if user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('student.dashboard'))
        else:
            log = AuditLog(ip_address=ip, email_attempted=email, status='failed')
            db.session.add(log)
            db.session.commit()
            flash("Incorrect password. Please try again", "danger")
            
    return render_template("auth/login.html")

def check_password_strength(password):
    score = 0
    if re.search(r'[A-Z]', password): score += 1
    if re.search(r'[a-z]', password): score += 1
    if re.search(r'[0-9]', password): score += 1
    if re.search(r'[@#$%^&*]', password): score += 1
    return score >= 4 and len(password) >= 8

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('student.dashboard'))
        
    if request.method == "POST":
        full_name = request.form.get("full_name")
        email = request.form.get("email")
        password = request.form.get("password")
        country = request.form.get("country", "Nepal")
        curriculum = COUNTRY_CURRICULUM_MAP.get(country, "National")
        level_of_study = request.form.get("level_of_study")
        program = request.form.get("program") if level_of_study in ("Class 11", "Class 12", "Bachelors", "Masters") else ""
        semester = request.form.get("semester") if level_of_study in ("Bachelors", "Masters") else ""

        # University (shown on registration for Bachelors / Masters, Nepal only)
        university = ""
        if level_of_study in ("Bachelors", "Masters"):
            uni_select = request.form.get("university_select", "").strip()
            uni_custom = request.form.get("university_custom", "").strip()
            if uni_select in ("Foreign-Affiliated", "Other"):
                university = f"{uni_select}: {uni_custom}" if uni_custom else uni_select
            else:
                university = uni_select
        
        # Auto-generate a unique student identifier internally
        import uuid
        student_number = f"STU-{uuid.uuid4().hex[:8].upper()}"
        
        # Resolve year_of_study
        year_of_study = 1
        if semester:
            if "Semester" in semester:
                try:
                    sem_num = int(semester.replace("Semester", "").strip())
                    year_of_study = (sem_num - 1) // 2 + 1
                except ValueError:
                    pass
            elif "Professional Year" in semester:
                try:
                    year_of_study = int(semester.replace("Professional Year", "").strip())
                except ValueError:
                    pass
        
        # Case-insensitive email duplicate check
        if User.query.filter(db.func.lower(User.email) == email.lower()).first():
            flash("This email is already registered. Please login", "danger")
            return redirect(url_for('auth.register'))
            
        if not check_password_strength(password):
            flash("Password does not meet strength requirements", "danger")
            return redirect(url_for('auth.register'))
            
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(username=email.lower(), full_name=full_name, email=email, password_hash=hashed_password, role='student')
        
        db.session.add(new_user)
        db.session.flush() # To get user ID
        
        profile = StudentProfile(
            user_id=new_user.id,
            student_number=student_number,
            program=program,
            year_of_study=year_of_study,
            level_of_study=level_of_study,
            study_level=level_of_study,
            semester=semester,
            country=country,
            university=university,
            timezone=default_timezone_for_country(country),
            curriculum=curriculum,
            cumulative_gpa=0.0
        )
        db.session.add(profile)
        
        # Seed default availability slots
        days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        default_slots = [
            {"start": "00:00", "end": "06:00", "category": "Sleep"},
            {"start": "08:00", "end": "17:00", "category": "Class/Academic"},
            {"start": "22:00", "end": "23:59", "category": "Sleep"}
        ]
        for day in days:
            for ds in default_slots:
                slot = AvailabilitySlot(
                    user_id=new_user.id,
                    day_of_week=day,
                    start_time=ds["start"],
                    end_time=ds["end"],
                    slot_type="Sleep" if ds["category"] == "Sleep" else "Busy",
                    category=ds["category"],
                    is_overnight=ds["start"] > ds["end"],
                )
                db.session.add(slot)
                
        db.session.commit()
        
        flash("Account created successfully! Please login", "success")

        return redirect(url_for('auth.login'))
        
    return render_template("auth/register.html", active_universities=University.query.filter_by(is_active=True).order_by(University.sort_order).all())

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('auth.login'))
