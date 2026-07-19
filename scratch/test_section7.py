"""Section 7 Test: Restart-free Live Configuration"""
import sys
sys.path.insert(0, '.')
import time
from app import create_app, db
from app.models import User, AppSetting
from app.live_config import load_live_config

app = create_app()
app.config['TESTING'] = True
errors = []

with app.app_context():
    admin = User.query.filter_by(role='admin').first()
    admin_id = admin.id

    # Test 1: Load config initially
    try:
        load_live_config(app, force=True)
        # Ensure it is in app.config
        assert app.config.get("GEMINI_MODEL_MCQ") is not None
        print(f"PASS: Dynamic config loaded to app.config: {app.config.get('GEMINI_MODEL_MCQ')}")
    except Exception as e:
        errors.append(f"FAIL initial load: {e}")
        print(f"FAIL: {e}")

    # Test 2: Modify via POST route and check instant update (cache reload)
    try:
        with app.test_client() as c:
            with c.session_transaction() as sess:
                sess['_user_id'] = str(admin_id)
                sess['_fresh'] = True
            
            # Post a new value for MCQ model
            test_model_name = "gemini-test-mcq-model-999"
            payload = {
                "GEMINI_MODEL_MCQ": test_model_name,
                "GEMINI_API_KEY": "fake_key",
                "ANTHROPIC_API_KEY": "",
                "GEMINI_MODEL_ASSISTANT_PRIMARY": "gemini-2.5-flash",
                "GEMINI_MODEL_ASSISTANT_FALLBACK": "gemini-2.5-flash-lite",
                "GEMINI_DAILY_LIMIT_MCQ": "500",
                "GEMINI_RPM_LIMIT_MCQ": "12",
                "GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY": "50",
                "GEMINI_DAILY_LIMIT_ASSISTANT_FALLBACK": "50",
                "GEMINI_RPM_LIMIT_ASSISTANT_PRIMARY": "5",
                "GEMINI_BILLING_ENABLED": "on"
            }
            r = c.post('/admin/config', data=payload, follow_redirects=True)
            assert r.status_code == 200
            
            # Check database value
            setting = AppSetting.query.get("GEMINI_MODEL_MCQ")
            assert setting.value == test_model_name, f"Expected {test_model_name}, got {setting.value}"
            
            # Check app.config value is updated instantly (via force=True inside the POST route)
            assert app.config.get("GEMINI_MODEL_MCQ") == test_model_name, f"Cache not cleared, app.config has {app.config.get('GEMINI_MODEL_MCQ')}"
            assert app.config.get("GEMINI_BILLING_ENABLED") is True
            print("PASS: POST route saves to DB and updates app.config instantly (cache reload)")
    except Exception as e:
        errors.append(f"FAIL POST route config update: {e}")
        print(f"FAIL: {e}")

    # Test 3: Caching TTL (60s)
    try:
        from app.live_config import _config_last_loaded
        
        # Manually alter database value for testing cache behavior
        setting = AppSetting.query.get("GEMINI_MODEL_MCQ")
        original_db_value = setting.value
        setting.value = "another-temporary-value"
        db.session.commit()
        
        # Trigger normal check_live_config hook execution (doesn't force reload)
        load_live_config(app)
        # Because we didn't force reload and timestamp is fresh, app.config should still hold test_model_name
        assert app.config.get("GEMINI_MODEL_MCQ") == test_model_name, "Cache reload triggered prematurely"
        print("PASS: Cache is maintained when within 60s TTL")
        
        # Simulate TTL expiration by backdating the last loaded timestamp
        import app.live_config as lc
        lc._config_last_loaded = time.time() - 65
        
        # Trigger dynamic config load again
        load_live_config(app)
        # Now it should pick up the database changes
        assert app.config.get("GEMINI_MODEL_MCQ") == "another-temporary-value", "Cache failed to reload after TTL expiration"
        print("PASS: Cache is automatically refreshed after 60s TTL expires")
        
        # Restore database value
        setting = AppSetting.query.get("GEMINI_MODEL_MCQ")
        setting.value = original_db_value
        db.session.commit()
        load_live_config(app, force=True)
    except Exception as e:
        errors.append(f"FAIL cache caching/TTL: {e}")
        print(f"FAIL: {e}")

if errors:
    print(f"\n=== Section 7: {len(errors)} FAILURE(S) ===")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)
else:
    print("\n=== Section 7: ALL TESTS PASSED ===")
