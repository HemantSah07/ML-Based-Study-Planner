from app import create_app, db
from app.models import User, StudentAssessment, AssessmentResponse, Subject

app = create_app()
with app.app_context():
    assessments = StudentAssessment.query.all()
    print(f"Total StudentAssessment records found: {len(assessments)}")
    for sa in assessments:
        user = User.query.get(sa.student_id)
        subj = Subject.query.get(sa.subject_id)
        resp_count = AssessmentResponse.query.filter_by(assessment_id=sa.id).count()
        correct_count = AssessmentResponse.query.filter_by(assessment_id=sa.id, is_correct=True).count()
        print(f"ID: {sa.id} | User: {user.email if user else 'Unknown'} | Subject: {subj.name if subj else 'Unknown'}")
        print(f"  total_score (flat_pct): {sa.total_score} | weighted_score: {sa.weighted_score} | tier: {sa.knowledge_tier}")
        print(f"  completed_at: {sa.completed_at}")
        print(f"  Responses: {resp_count} (Correct: {correct_count})")
        print("-" * 50)
