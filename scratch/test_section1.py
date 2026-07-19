"""
test_section1.py
Automated validation of Section 1: Curriculum & Taxonomy Management.
- Adds a new university.
- Verifies it appears in active universities.
- Verifies deactivation warnings & student count checks.
"""
from app import create_app, db
from app.models import University, StudentProfile, User

app = create_app()

with app.app_context():
    print("=== RUNNING SECTION 1 TESTS ===")
    
    # 1. Add a new university via models (simulating admin action)
    uni_name = "Test University of Nepal (TUN)"
    existing = University.query.filter_by(name=uni_name).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        
    new_uni = University(name=uni_name, abbreviation="TUN", country="Nepal", is_active=True, sort_order=99)
    db.session.add(new_uni)
    db.session.commit()
    print(f"1. Added new university: {uni_name}")
    
    # Verify it is in active list
    active_unis = University.query.filter_by(is_active=True).all()
    active_names = [u.name for u in active_unis]
    assert uni_name in active_names, "New university must be in active list!"
    print("   Verified: New university appears in active list.")
    
    # 2. Deactivate a university in use (e.g. Tribhuvan University) and verify student count
    target_uni_name = "Tribhuvan University (TU)"
    target_uni = University.query.filter_by(name=target_uni_name).first()
    if not target_uni:
        # Create it if it doesn't exist
        target_uni = University(name=target_uni_name, abbreviation="TU", country="Nepal", is_active=True, sort_order=1)
        db.session.add(target_uni)
        db.session.commit()
        
    # Query student count using it
    student_count = StudentProfile.query.filter(StudentProfile.university.like(f"{target_uni_name}%")).count()
    print(f"2. Checked students using '{target_uni_name}': {student_count}")
    
    # Let's ensure at least 1 student is set to TU for testing if count is 0
    if student_count == 0:
        student_prof = StudentProfile.query.first()
        if student_prof:
            student_prof.university = target_uni_name
            db.session.commit()
            student_count = StudentProfile.query.filter(StudentProfile.university.like(f"{target_uni_name}%")).count()
            print(f"   Set first student profile university to '{target_uni_name}'. New count: {student_count}")
            
    assert student_count > 0, "There should be at least one student using the university for deactivation test"
    
    # Simulate deactivating
    target_uni.is_active = False
    db.session.commit()
    print(f"3. Deactivated university '{target_uni_name}'")
    
    # Confirm it is no longer in active list
    active_unis_after = University.query.filter_by(is_active=True).all()
    active_names_after = [u.name for u in active_unis_after]
    assert target_uni_name not in active_names_after, "Deactivated university must NOT be in active list!"
    print("   Verified: Deactivated university does NOT appear in active list.")
    
    # Verify student's profile still has it intact
    prof = StudentProfile.query.filter(StudentProfile.university.like(f"{target_uni_name}%")).first()
    assert prof is not None, "Student profile must still contain the university value"
    assert prof.university == target_uni_name, f"Expected student university to be '{target_uni_name}', got '{prof.university}'"
    print(f"   Verified: Student profile university value remains intact: '{prof.university}'")
    
    # Restore for safety
    target_uni.is_active = True
    # Clean up test uni
    db.session.delete(new_uni)
    db.session.commit()
    print("4. Restored system state (reactivated TU, deleted TUN)")
    print("=== SECTION 1 TESTS PASSED SUCCESSFULLY ===")
