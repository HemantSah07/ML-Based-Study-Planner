"""Regression test: verify admin blueprint imports and routes resolve."""
import sys, os
sys.path.insert(0, '.')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

from app import create_app
app = create_app()
print("OK: App created OK")

with app.app_context():
    rules = [r for r in app.url_map.iter_rules() if r.endpoint.startswith('admin.')]
    print(f"OK: Total admin routes: {len(rules)}")
    expected_routes = [
        '/admin/content/questions/regenerate/<int:subject_id>',
        '/admin/content/chapters/<int:subject_id>/topics',
        '/admin/students/<int:student_id>/regenerate-schedule',
        '/admin/analytics/detail',
        '/admin/config/planner',
        '/admin/bulk/seed-questions',
        '/admin/bulk/seed-questions/status',
        '/admin/bulk/seed-questions/stop',
        '/admin/bulk/export-students',
        '/admin/bulk/export-students-json',
        '/admin/bulk/import-curriculum',
        '/admin/content/stats',
        '/admin/content/pdfs/regenerate/<int:topic_id>',
        '/admin/health',
        '/admin/config',
        '/admin/analytics',
        '/admin/bulk',
        '/admin/students',
        '/admin/students/<int:student_id>',
    ]
    rule_set = {r.rule for r in rules}
    all_pass = True
    for route in expected_routes:
        found = route in rule_set
        status = "OK" if found else "MISSING"
        if not found:
            all_pass = False
        print(f"  {status}  {route}")

    student_rules = [r for r in app.url_map.iter_rules() if r.endpoint.startswith('student.')]
    print(f"OK: Student routes intact: {len(student_rules)}")
    auth_rules = [r for r in app.url_map.iter_rules() if r.endpoint.startswith('auth.')]
    print(f"OK: Auth routes intact: {len(auth_rules)}")

    print("\n" + ("ALL CHECKS PASSED" if all_pass else "SOME ROUTES MISSING -- see above"))
