from flask import Flask
from flask_login import LoginManager
from flask_mail import Mail, Message
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['UPLOAD_FOLDER'] = "static/uploads"
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

app.config['MIDTRANS_SERVER_KEY'] = os.getenv('MIDTRANS_SERVER_KEY')
app.config['MIDTRANS_CLIENT_KEY'] = os.getenv('MIDTRANS_CLIENT_KEY')
# env kamu bentuknya string, jadi di-cast ke bool
app.config['MIDTRANS_IS_PRODUCTION'] = (
    os.getenv('MIDTRANS_IS_PRODUCTION', 'false').lower() == 'true'
)

# (opsional, kalau mau dipakai nanti)
app.config['MIDTRANS_MERCHANT_ID'] = os.getenv('MIDTRANS_MERCHANT_ID')

# --- Mail Configuration ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')

mail = Mail(app)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth_controller.auth_login'
login_manager.login_message = 'Silakan login untuk mengakses halaman ini.'

# Import models dan utils
from models.user_model import User
from utils.database import init_db

# Import controllers
from controllers.auth_controller import auth_controller
from controllers.comprof_controller import comprof_controller
from controllers.eggmart_controller import eggmart_controller
from controllers.eggmonitor_controller import eggmonitor_controller
from controllers.eggmin_controller import eggmin_controller
from controllers.chat_controller import chat_controller

# Register blueprints
app.register_blueprint(auth_controller)
app.register_blueprint(comprof_controller)
app.register_blueprint(eggmart_controller, url_prefix='/eggmart')
app.register_blueprint(eggmonitor_controller, url_prefix='/eggmonitor')
app.register_blueprint(eggmin_controller, url_prefix='/eggmin')
app.register_blueprint(chat_controller)

# User loader untuk Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(user_id)

# Initialize database
with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5001)