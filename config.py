import os
from dotenv import load_dotenv

load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'eggvision'),
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci'
}

# ML Model configuration
MODEL_PATH = "static/cangkang-cnn.keras"
CLASS_NAMES = ["Brown", "DarkBrown", "LightBrown"]
UPLOAD_FOLDER = "static/uploads"

# App configuration
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')

MIDTRANS_SERVER_KEY = os.getenv("MIDTRANS_SERVER_KEY")
MIDTRANS_CLIENT_KEY = os.getenv("MIDTRANS_CLIENT_KEY")
MIDTRANS_IS_PRODUCTION = os.getenv("MIDTRANS_IS_PRODUCTION", "false").lower() == "true"
