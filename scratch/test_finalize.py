from app import create_app, db
from app.models import StudentAssessment, AssessmentResponse, AssessmentQuestion

app = create_app()
with app.app_context():
    sa_id = 20
    sa_row = StudentAssessment.query.get(sa_id)
    if not sa_row:
        print(f"StudentAssessment {sa_id} not found.")
        exit(1)
        
    print(f"Original StudentAssessment total_score: {sa_row.total_score}")
    
    responses = AssessmentResponse.query.filter_by(assessment_id=sa_id).all()
    total_q = len(responses)
    correct = sum(1 for r in responses if r.is_correct)
    
    w_pts = 0.0
    m_pts = 0.0
    for r in responses:
        q = AssessmentQuestion.query.get(r.question_id)
        weight = 1.0
        if q:
            diff = (q.difficulty or "").lower()
            if diff in ("medium", "intermediate"):
                weight = 1.5
            elif diff in ("hard", "advanced"):
                weight = 2.0
        m_pts += weight
        if r.is_correct:
            w_pts += weight
            
    flat_pct = (correct / total_q) * 100
    weighted_pct = (w_pts / m_pts * 100) if m_pts > 0 else 0.0
    
    tier = 'beginner'
    if weighted_pct >= 70: tier = 'advanced'
    elif weighted_pct >= 40: tier = 'intermediate'
    
    print(f"Calculated: flat_pct={flat_pct}, weighted_pct={weighted_pct}, tier={tier}")
    
    sa_row.total_score = flat_pct
    sa_row.weighted_score = weighted_pct
    sa_row.knowledge_tier = tier
    
    print(f"Assigned values to sa_row: total_score={sa_row.total_score}, weighted_score={sa_row.weighted_score}, knowledge_tier={sa_row.knowledge_tier}")
    
    db.session.commit()
    print("db.session.commit() executed.")
    
    # Reload from DB
    db.session.expire(sa_row)
    reloaded_sa = StudentAssessment.query.get(sa_id)
    print(f"Reloaded total_score: {reloaded_sa.total_score}")
