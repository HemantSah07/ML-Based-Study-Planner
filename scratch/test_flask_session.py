import os
from flask import session
from app import create_app, db
from app.models import User, Subject, AssessmentQuestion, StudentSeenQuestion

app = create_app()
app.config['TESTING'] = True

with app.test_client() as client:
    # 1. Log in user 709 (hemant@gmail.com)
    with client.session_transaction() as sess:
        sess['_user_id'] = '709'
        sess['_fresh'] = True
    
    # 2. Call assessment_start to initialize scores
    res = client.post('/assessment/start', data={'subjects': ['340']})
    print("Redirect from start:", res.status_code, res.location)

    # Check session after start
    with client.session_transaction() as sess:
        print("Session assessment_scores after start:", sess.get('assessment_scores'))
        print("Session assessment_subjects:", sess.get('assessment_subjects'))

    # Let's get the first question for subject 340
    with app.app_context():
        q = AssessmentQuestion.query.filter_by(subject_id=340).first()
        q_id = q.id
        correct_ans = q.correct_answer
        print(f"Testing Question ID: {q_id}, correct answer: {correct_ans}")

    # 3. Call assessment_answer to answer question 1 correctly
    res = client.post('/assessment/answer', data={
        'question_id': str(q_id),
        'subject_id': '340',
        'q_num': '1',
        'answer': correct_ans,
        'time_taken': '10'
    })
    print("Redirect from answer 1:", res.status_code, res.location)

    # Check session after answer 1
    with client.session_transaction() as sess:
        print("Session assessment_scores after answer 1:", sess.get('assessment_scores'))

    # 4. Call assessment_answer to answer question 2 incorrectly (or empty)
    res = client.post('/assessment/answer', data={
        'question_id': str(q_id), # reuse q_id for simplicity in testing session persistence
        'subject_id': '340',
        'q_num': '2',
        'answer': 'X', # incorrect
        'time_taken': '15'
    })
    print("Redirect from answer 2:", res.status_code, res.location)

    # Check session after answer 2
    with client.session_transaction() as sess:
        print("Session assessment_scores after answer 2:", sess.get('assessment_scores'))
