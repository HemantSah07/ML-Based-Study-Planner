with open('app/routes/auth.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Clean up imports and the register return
content = content.replace(
    "from app.models import User, AuditLog, StudentProfile, AvailabilitySlot",
    "from app.models import User, AuditLog, StudentProfile, AvailabilitySlot, University"
)

content = content.replace(
    'from app.models import User, AuditLog, StudentProfile, AvailabilitySlot, University\n# ...\n    return render_template("auth/register.html", active_universities=University.query.filter_by(is_active=True).order_by(University.sort_order).all())',
    'return render_template("auth/register.html", active_universities=University.query.filter_by(is_active=True).order_by(University.sort_order).all())'
)

with open('app/routes/auth.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("SUCCESS: cleaned auth.py")
