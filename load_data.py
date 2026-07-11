import argparse
import os
import pandas as pd
from app import create_app, db, bcrypt
from app.models import User, Subject, StudentProfile

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "instance", "data")
DEMO_PASSWORD = "Student@123"

app = create_app()


def load_seed_data(fresh=False):
    with app.app_context():
        if fresh:
            db.drop_all()
            db.create_all()
            print("Database reset (drop_all + create_all).")
        else:
            db.create_all()

        subjects_df = pd.read_csv(os.path.join(DATA_DIR, "03_subjects.csv"))
        for _, row in subjects_df.iterrows():
            if Subject.query.filter_by(code=row["code"]).first():
                continue
            db.session.add(
                Subject(
                    id=int(row["id"]),
                    code=row["code"],
                    name=row["name"],
                    credit_hours=int(row["credit_hours"]),
                    difficulty_level=int(row["difficulty_level"]),
                    semester_tag=row["semester_tag"],
                )
            )
        db.session.commit()
        print(f"Subjects loaded: {Subject.query.count()}")

        demo_hash = bcrypt.generate_password_hash(DEMO_PASSWORD).decode("utf-8")
        users_df = pd.read_csv(os.path.join(DATA_DIR, "01_users.csv"))
        for _, row in users_df.iterrows():
            if User.query.filter_by(email=row["email"]).first():
                continue
            db.session.add(
                User(
                    id=int(row["id"]),
                    username=row["email"].lower(),
                    full_name=row["full_name"],
                    email=row["email"],
                    password_hash=demo_hash,
                    role=row["role"],
                    is_active=bool(int(row["is_active"])),
                )
            )
        db.session.commit()
        print(f"Users loaded: {User.query.count()}")

        profiles_df = pd.read_csv(os.path.join(DATA_DIR, "02_student_profiles.csv"))
        for _, row in profiles_df.iterrows():
            if StudentProfile.query.filter_by(user_id=int(row["user_id"])).first():
                continue
            db.session.add(
                StudentProfile(
                    id=int(row["id"]),
                    user_id=int(row["user_id"]),
                    student_number=row["student_number"],
                    program=row["program"],
                    year_of_study=int(row["year_of_study"]),
                    cumulative_gpa=float(row["cumulative_gpa"]),
                )
            )
        db.session.commit()
        print(f"Student profiles loaded: {StudentProfile.query.count()}")
        print(f"Data loading complete! Demo login: any seeded email + password {DEMO_PASSWORD}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load Smart Study seed data")
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Drop and recreate all tables before loading (destructive)",
    )
    args = parser.parse_args()
    load_seed_data(fresh=args.fresh)
