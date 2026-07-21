from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db, bcrypt
from app.models import User, AuditLog, StudentProfile, AvailabilitySlot, University, EmailVerificationCode
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

        # Seed accounts created by load_data.py are not loginable.
        if getattr(user, 'is_seed_account', False):
            log = AuditLog(ip_address=ip, email_attempted=email, status='failed')
            db.session.add(log)
            db.session.commit()
            flash("No account found with this email address", "danger")
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
            
        # Email verification check using Abstract API
        from app.utils.email_verification import verify_email
        verification = verify_email(email)
        
        # Block ONLY if format is invalid OR if deliverability is explicitly UNDELIVERABLE
        if not verification.get("is_valid_format") or verification.get("deliverability") == "UNDELIVERABLE":
            flash("This email address doesn't appear to be valid or deliverable, please check and try again", "danger")
            return redirect(url_for('auth.register'))
            
        # ── 1. Generate a cryptographically secure 6-digit code ──────────────────
        import secrets
        code = "".join(secrets.choice("0123456789") for _ in range(6))
        
        now = datetime.utcnow()
        expires = now + timedelta(minutes=10)
        
        # Clear any existing code for this email first
        EmailVerificationCode.query.filter_by(email=email).delete()
        
        verification_code = EmailVerificationCode(
            email=email,
            code=code,
            created_at=now,
            expires_at=expires,
            verified=False,
            attempts=0
        )
        db.session.add(verification_code)
        db.session.commit()
        
        # ── 2. Store registration data temporarily in the session ────────────────
        from flask import session
        session['temp_registration'] = {
            'email': email,
            'full_name': full_name,
            'password': password,
            'country': country,
            'curriculum': curriculum,
            'level_of_study': level_of_study,
            'program': program,
            'semester': semester,
            'university': university,
            'student_number': student_number,
            'year_of_study': year_of_study,
            'email_verified_status': verification.get("deliverability", "unknown").lower()
        }
        session['resend_count'] = 0
        session['last_resend_time'] = None

        # ── 3. Send verification code email via Flask-Mail ───────────────────────
        from flask_mail import Message
        from app import mail
        try:
            msg = Message(
                subject="Verify Your Email - Smart Study",
                recipients=[email],
                body=f"Your Smart Study verification code is: {code}. This code expires in 10 minutes."
            )
            mail.send(msg)
            flash("A 6-digit verification code has been sent to your email.", "info")
        except Exception as e:
            flash(f"Failed to send verification email: {e}. Please try again later.", "danger")
            return redirect(url_for('auth.register'))
            
        return redirect(url_for('auth.verify_email_code', email=email))
        
    return render_template("auth/register.html", active_universities=University.query.filter_by(is_active=True).order_by(University.sort_order).all())


@auth_bp.route("/verify-email", methods=["GET", "POST"])
def verify_email_code():
    from flask import session
    email = request.args.get("email")
    if not email:
        flash("Email parameter missing.", "danger")
        return redirect(url_for('auth.register'))
        
    temp_data = session.get('temp_registration')
    if not temp_data or temp_data.get('email') != email:
        flash("Session expired or invalid email. Please register again.", "danger")
        return redirect(url_for('auth.register'))
        
    resend_count = session.get('resend_count', 0)
    
    # Calculate remaining time for the 60-second resend cooldown
    time_remaining = 0
    last_resend_time_str = session.get('last_resend_time')
    if last_resend_time_str:
        try:
            last_resend_time = datetime.fromisoformat(last_resend_time_str)
            elapsed = (datetime.utcnow() - last_resend_time).total_seconds()
            if elapsed < 60:
                time_remaining = int(60 - elapsed)
        except Exception:
            pass

    code_record = EmailVerificationCode.query.filter_by(email=email).order_by(EmailVerificationCode.created_at.desc()).first()
    if not code_record:
        flash("No verification code found. Please request a new one.", "danger")
        return redirect(url_for('auth.register'))
        
    # Expiration check
    if datetime.utcnow() > code_record.expires_at:
        session.pop('temp_registration', None)
        flash("Verification code has expired. Please register again.", "danger")
        return redirect(url_for('auth.register'))

    if request.method == "POST":
        user_code = request.form.get("code", "").strip()
        
        # 1. Attempt limit check
        if code_record.attempts >= 5:
            flash("Too many failed attempts. Please request a new code.", "danger")
            return render_template("auth/verify_email.html", email=email, resend_count=resend_count, time_remaining=time_remaining)
            
        # 2. Code check
        if code_record.code != user_code:
            code_record.attempts += 1
            db.session.commit()
            
            remaining = 5 - code_record.attempts
            if remaining <= 0:
                flash("Too many failed attempts. Please request a new code.", "danger")
            else:
                flash(f"Invalid verification code. {remaining} attempt(s) remaining.", "danger")
            return render_template("auth/verify_email.html", email=email, resend_count=resend_count, time_remaining=time_remaining)
            
        # Successful code verification
        code_record.verified = True
        db.session.commit()
        
        # Create User record
        hashed_password = bcrypt.generate_password_hash(temp_data['password']).decode('utf-8')
        new_user = User(
            username=temp_data['email'].lower(),
            full_name=temp_data['full_name'],
            email=temp_data['email'],
            password_hash=hashed_password,
            role='student',
            email_verified_status=temp_data['email_verified_status']
        )
        db.session.add(new_user)
        db.session.flush()
        
        # Create StudentProfile record
        profile = StudentProfile(
            user_id=new_user.id,
            student_number=temp_data['student_number'],
            program=temp_data['program'],
            year_of_study=temp_data['year_of_study'],
            level_of_study=temp_data['level_of_study'],
            study_level=temp_data['level_of_study'],
            semester=temp_data['semester'],
            country=temp_data['country'],
            university=temp_data['university'],
            timezone=default_timezone_for_country(temp_data['country']),
            curriculum=temp_data['curriculum'],
            cumulative_gpa=0.0
        )
        db.session.add(profile)
        
        # Seed availability slots
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
        
        # Log student in and clear temp data
        login_user(new_user)
        session.pop('temp_registration', None)
        flash("Email verified and account created successfully!", "success")
        return redirect(url_for('student.dashboard'))
        
    return render_template("auth/verify_email.html", email=email, resend_count=resend_count, time_remaining=time_remaining)


@auth_bp.route("/resend-code", methods=["POST"])
def resend_verification_code():
    from flask import session
    email = request.args.get("email")
    if not email:
        flash("Email parameter missing.", "danger")
        return redirect(url_for('auth.register'))
        
    temp_data = session.get('temp_registration')
    if not temp_data or temp_data.get('email') != email:
        flash("Session expired or invalid email. Please register again.", "danger")
        return redirect(url_for('auth.register'))
        
    resend_count = session.get('resend_count', 0)
    
    # 1. Count limit
    if resend_count >= 3:
        flash("Maximum resend attempts reached (3). Please complete verification or start over.", "danger")
        return redirect(url_for('auth.verify_email_code', email=email))
        
    # 2. Wait limit check
    last_resend_time_str = session.get('last_resend_time')
    if last_resend_time_str:
        try:
            last_resend_time = datetime.fromisoformat(last_resend_time_str)
            elapsed = (datetime.utcnow() - last_resend_time).total_seconds()
            if elapsed < 60:
                flash(f"Please wait {int(60 - elapsed)} second(s) before resending.", "danger")
                return redirect(url_for('auth.verify_email_code', email=email))
        except Exception:
            pass

    # 3. Generate new code and save
    import secrets
    code = "".join(secrets.choice("0123456789") for _ in range(6))
    
    now = datetime.utcnow()
    expires = now + timedelta(minutes=10)
    
    # Clean previous codes
    EmailVerificationCode.query.filter_by(email=email).delete()
    
    verification_code = EmailVerificationCode(
        email=email,
        code=code,
        created_at=now,
        expires_at=expires,
        verified=False,
        attempts=0
    )
    db.session.add(verification_code)
    db.session.commit()
    
    session['resend_count'] = resend_count + 1
    session['last_resend_time'] = datetime.utcnow().isoformat()
    
    # 4. Send code
    from flask_mail import Message
    from app import mail
    try:
        msg = Message(
            subject="Verify Your Email - Smart Study",
            recipients=[email],
            body=f"Your Smart Study verification code is: {code}. This code expires in 10 minutes."
        )
        mail.send(msg)
        flash("A new 6-digit verification code has been sent to your email.", "success")
    except Exception as e:
        flash(f"Failed to send verification email: {e}. Please try again later.", "danger")
        
    return redirect(url_for('auth.verify_email_code', email=email))

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('auth.login'))
