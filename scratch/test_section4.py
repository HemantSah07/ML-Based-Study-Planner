"""Section 4 Test: System Health Dashboard"""
import sys
sys.path.insert(0, '.')
from app import create_app
from app.models import User

app = create_app()
app.config['TESTING'] = True
errors = []

with app.app_context():
    admin = User.query.filter_by(role='admin').first()
    admin_id = admin.id

    # Test 1: health check helper functions
    try:
        from app.routes.admin import _check_db, _check_ml_model, _get_disk_info, _get_python_info, _get_model_config
        db_r = _check_db()
        ml_r = _check_ml_model()
        disk_r = _get_disk_info()
        py_r = _get_python_info()
        mc_r = _get_model_config()
        assert db_r.get('status') in ('ok', 'error', 'warning'), f'DB check bad status: {db_r}'
        assert ml_r.get('status') in ('ok', 'missing', 'error'), f'ML check bad status: {ml_r}'
        assert 'version' in py_r, 'Python info missing version'
        assert len(mc_r) == 3, f'Expected 3 model configs, got {len(mc_r)}'
        print(f"PASS: DB={db_r['status']}  ML={ml_r['status']}  disk_free={disk_r.get('free_gb')}GB  py={py_r['version']}")
    except Exception as e:
        errors.append(f'FAIL health logic: {e}')
        print(f'FAIL: {e}')

    # Test 2: health route renders
    try:
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess['_user_id'] = str(admin_id)
                sess['_fresh'] = True
            r = c.get('/admin/health', follow_redirects=True)
            assert r.status_code == 200, f'Expected 200 got {r.status_code}'
            assert b'System Health' in r.data, 'System Health title not in page'
        print('PASS: /admin/health renders 200 with title')
    except Exception as e:
        errors.append(f'FAIL health route: {e}')
        print(f'FAIL: {e}')

    # Test 3: check all required template context keys
    try:
        with app.test_request_context():
            from flask_login import login_user
            login_user(admin)
            from app.routes.admin import _check_db, _check_ml_model, _check_gemini_api, _get_disk_info, _get_python_info, _get_model_config
            checks = {'db': _check_db(), 'gemini': _check_gemini_api(), 'ml': _check_ml_model()}
            for key in ('db', 'gemini', 'ml'):
                assert 'status' in checks[key], f'Missing status key in {key}'
            print(f"PASS: All health check keys present. Gemini={checks['gemini']['status']}")
    except Exception as e:
        errors.append(f'FAIL health keys: {e}')
        print(f'FAIL: {e}')

if errors:
    print(f'\n=== Section 4: {len(errors)} FAILURE(S) ===')
    for e in errors:
        print(f'  {e}')
    sys.exit(1)
else:
    print('\n=== Section 4: ALL TESTS PASSED ===')
