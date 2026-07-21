from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_mail import Mail
from config import Config

db            = SQLAlchemy()
bcrypt        = Bcrypt()
login_manager = LoginManager()
mail          = Mail()
login_manager.login_view             = "auth.login"
login_manager.login_message_category = "warning"

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)

    with app.app_context():
        from app.live_config import load_live_config
        load_live_config(app, force=True)

    @app.before_request
    def check_live_config():
        from app.live_config import load_live_config
        load_live_config(app)

    from app.routes.auth    import auth_bp
    from app.routes.student import student_bp
    from app.routes.admin   import admin_bp
    from app.routes.main    import main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp, url_prefix="/student")
    app.register_blueprint(admin_bp,   url_prefix="/admin")

    return app