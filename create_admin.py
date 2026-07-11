from app import create_app, db
from app.models import User
from flask_bcrypt import Bcrypt

app = create_app()
bcrypt = Bcrypt(app)

with app.app_context():
    # Check if admin already exists to prevent duplicate entries if run multiple times
    if not User.query.filter_by(email='admin@gmail.com').first():
        admin = User(
            username='Admin User',
            email='admin@gmail.com',
            password_hash=bcrypt.generate_password_hash('Admin@5916').decode('utf-8'),
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()
        print('Admin created successfully!')
    else:
        print('Admin user already exists!')

