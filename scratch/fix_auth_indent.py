with open('app/routes/auth.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if "from app.models import User, AuditLog, StudentProfile, AvailabilitySlot, University, University" in line:
        skip = True
        continue
    if skip and "# ..." in line:
        continue
    if skip and 'return render_template("auth/register.html", active_universities=' in line:
        new_lines.append('    return render_template("auth/register.html", active_universities=University.query.filter_by(is_active=True).order_by(University.sort_order).all())\n')
        skip = False
        continue
    new_lines.append(line)

with open('app/routes/auth.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("SUCCESS: cleaned auth.py register return")
