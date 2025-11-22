from flask import Flask
from flask_login import LoginManager
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['UPLOAD_FOLDER'] = "static/uploads"
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- Mail Configuration ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')

mail = Mail(app)

# Configure Upload Folder
UPLOAD_FOLDER = 'static/uploads/products'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# MySQL configuration
db_config = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'eggvision'),
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci'
}

# (opsional, kalau mau dipakai nanti)
app.config['MIDTRANS_MERCHANT_ID'] = os.getenv('MIDTRANS_MERCHANT_ID')

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
