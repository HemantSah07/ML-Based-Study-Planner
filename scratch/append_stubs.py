"""
Append stubs for all missing admin nav routes — prevents Jinja url_for errors.
These will be replaced by full implementations in each section.
"""

stubs = '''

# ── SECTION 4 STUB: HEALTH ────────────────────────────────────────────────────
@admin_bp.route("/health")
def health():
    return render_template("admin/health.html")


# ── SECTION 2 STUB: CONTENT ──────────────────────────────────────────────────
@admin_bp.route("/content")
def content_subjects():
    return render_template("admin/content/subjects.html")


# ── SECTION 5 STUB: ANALYTICS ────────────────────────────────────────────────
@admin_bp.route("/analytics")
def analytics():
    return render_template("admin/analytics.html")


# ── SECTION 7 STUB: CONFIG ───────────────────────────────────────────────────
@admin_bp.route("/config")
def config():
    return render_template("admin/config.html")


# ── SECTION 8 STUB: BULK OPS ─────────────────────────────────────────────────
@admin_bp.route("/bulk")
def bulk():
    return render_template("admin/bulk.html")
'''

with open('app/routes/admin.py', 'a', encoding='utf-8') as f:
    f.write(stubs)

print("SUCCESS: Stubs appended to admin.py")
