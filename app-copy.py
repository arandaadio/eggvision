from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import math
from werkzeug.utils import secure_filename
import os
import numpy as np
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import load_img, img_to_array

from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


MODEL_PATH = "static/cangkang-cnn.keras"  # Pastikan file model diletakkan di sini
model = load_model(MODEL_PATH)

# Kelas prediksi model (sesuaikan dengan model Anda)
CLASS_NAMES = ["Brown","DarkBrown","LightBrown"]

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)



app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return redirect(url_for("index"))

    file = request.files["file"]
    if file.filename == "":
        return redirect(url_for("index"))

    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(file_path)

    # --- Image preprocessing (sesuaikan dengan input model Anda) ---
    img = load_img(file_path, target_size=(224, 224))  # ubah size sesuai model
    img_array = img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0) / 255.0

    # Predict
    pred = model.predict(img_array)
    class_idx = np.argmax(pred)
    prediction_label = CLASS_NAMES[class_idx]
    confidence = float(np.max(pred) * 100)

    return render_template(
        "eggmonitor/index.html",
        **build_dashboard_data(),
        uploaded_image=url_for("static", filename=f"uploads/{filename}"),
        prediction=prediction_label,
        confidence=f"{confidence:.2f}%"
    )


app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

# MySQL configuration
db_config = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'ReksaSyahputra1012!'),
    'database': os.getenv('DB_NAME', 'eggvision'),
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci'
}

def get_db_connection():
    """Get MySQL database connection"""
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as e:
        print(f"Database connection error: {e}")
        return None

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth_login'
login_manager.login_message = 'Silakan login untuk mengakses halaman ini.'

# User model
class User(UserMixin):
    def __init__(self, id, name, email, password, role, created_at):
        self.id = id
        self.name = name
        self.email = email
        self.password = password
        self.role = role
        self.created_at = created_at

    @staticmethod
    def get_by_id(user_id):
        conn = get_db_connection()
        if not conn:
            return None
            
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user_data = cur.fetchone()
            cur.close()
            
            if user_data:
                return User(
                    id=user_data['id'],
                    name=user_data['name'],
                    email=user_data['email'],
                    password=user_data['password'],
                    role=user_data['role'],
                    created_at=user_data['created_at']
                )
            return None
        except mysql.connector.Error as e:
            print(f"Database error in get_by_id: {e}")
            return None
        finally:
            if conn:
                conn.close()

    @staticmethod
    def get_by_email(email):
        conn = get_db_connection()
        if not conn:
            return None
            
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            user_data = cur.fetchone()
            cur.close()
            
            if user_data:
                return User(
                    id=user_data['id'],
                    name=user_data['name'],
                    email=user_data['email'],
                    password=user_data['password'],
                    role=user_data['role'],
                    created_at=user_data['created_at']
                )
            return None
        except mysql.connector.Error as e:
            print(f"Database error in get_by_email: {e}")
            return None
        finally:
            if conn:
                conn.close()

@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(user_id)

# Database initialization
def init_db():
    conn = get_db_connection()
    if not conn:
        print("❌ Failed to connect to database")
        return
        
    try:
        cur = conn.cursor()
        
        # Create users table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                role ENUM('guest', 'pembeli', 'pengusaha', 'admin') DEFAULT 'guest',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create products table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                price DECIMAL(10,2) NOT NULL,
                grade ENUM('A', 'B', 'C') NOT NULL,
                stock INT DEFAULT 0,
                image_url VARCHAR(500),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        ''')
        
        # Create orders table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                total DECIMAL(10,2) NOT NULL,
                status ENUM('pending', 'paid', 'shipped', 'delivered', 'cancelled') DEFAULT 'pending',
                shipping_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        ''')
        
        # Create order_items table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS order_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                order_id INT,
                product_id INT,
                quantity INT NOT NULL,
                price DECIMAL(10,2) NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
            )
        ''')
        
        # Create news table for Comprof
        cur.execute('''
            CREATE TABLE IF NOT EXISTS news (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                image_url VARCHAR(500),
                is_published BOOLEAN DEFAULT FALSE,
                published_at TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Check if admin user exists
        cur.execute("SELECT COUNT(*) as count FROM users WHERE role = 'admin'")
        result = cur.fetchone()
        admin_count = result[0] if result else 0
        
        if admin_count == 0:
            hashed_password = generate_password_hash('eggmin123', method='pbkdf2:sha256')
            cur.execute(
                "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                ('EggMin Admin', 'eggmin@eggvision.com', hashed_password, 'admin')
            )
            print("✅ Admin user created: eggmin@eggvision.com / eggmin123")
        
        # Check if pembeli user exists
        cur.execute("SELECT COUNT(*) as count FROM users WHERE email = 'pembeli@eggvision.com'")
        result = cur.fetchone()
        pembeli_count = result[0] if result else 0
        
        if pembeli_count == 0:
            hashed_password = generate_password_hash('pembeli123',method='pbkdf2:sha256')
            cur.execute(
                "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                ('Budi Santoso', 'pembeli@eggvision.com', hashed_password, 'pembeli')
            )
            print("✅ Pembeli user created: pembeli@eggvision.com / pembeli123")
        
        # Check if pengusaha user exists
        cur.execute("SELECT COUNT(*) as count FROM users WHERE email = 'pengusaha@eggvision.com'")
        result = cur.fetchone()
        pengusaha_count = result[0] if result else 0
        
        if pengusaha_count == 0:
            hashed_password = generate_password_hash('pengusaha123', method='pbkdf2:sha256')
            cur.execute(
                "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                ('Sari Farm', 'pengusaha@eggvision.com', hashed_password, 'pengusaha')
            )
            print("✅ Pengusaha user created: pengusaha@eggvision.com / pengusaha123")
        
        # Check if products exist
        cur.execute("SELECT COUNT(*) as count FROM products")
        result = cur.fetchone()
        product_count = result[0] if result else 0
        
        if product_count == 0:
            # Get pengusaha user id
            cur.execute("SELECT id FROM users WHERE email = 'pengusaha@eggvision.com'")
            result = cur.fetchone()
            pengusaha_id = result[0] if result else 1
            
            sample_products = [
                ('Telur Ayam Grade A', 'Telur ayam segar Grade A dengan kualitas terbaik. Berat >60g, kulit tebal, bersih, dan segar.', 28000.00, 'A', 50, '/static/images/egg-grade-a.jpg', pengusaha_id),
                ('Telur Ayam Grade B', 'Telur ayam Grade B dengan kualitas baik. Gagal 1 parameter mutu utama tapi tetap segar.', 22000.00, 'B', 30, '/static/images/egg-grade-b.jpg', pengusaha_id),
                ('Telur Ayam Grade C', 'Telur ayam Grade C untuk kebutuhan industri. Gagal 2 parameter mutu utama tapi tidak retak/busuk.', 18000.00, 'C', 20, '/static/images/egg-grade-c.jpg', pengusaha_id),
            ]
            
            for product in sample_products:
                cur.execute(
                    "INSERT INTO products (name, description, price, grade, stock, image_url, user_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    product
                )
            print("✅ Sample products created for EggMart")
        
        # Check if news exist
        cur.execute("SELECT COUNT(*) as count FROM news")
        result = cur.fetchone()
        news_count = result[0] if result else 0
        
        if news_count == 0:
            sample_news = [
                ('EggVision Resmi Diluncurkan!', 'Platform revolusioner untuk industri peternakan telur Indonesia akhirnya resmi diluncurkan. EggVision menghadirkan solusi lengkap dari grading otomatis hingga marketplace terintegrasi.', '/static/images/news-launch.jpg', True, '2024-11-01 10:00:00'),
                ('Teknologi AI dalam Grading Telur', 'Bagaimana machine learning dan computer vision mengubah cara grading telur secara otomatis dengan akurasi mencapai 98%.', '/static/images/news-ai.jpg', True, '2024-11-05 14:30:00'),
            ]
            
            for news in sample_news:
                cur.execute(
                    "INSERT INTO news (title, content, image_url, is_published, published_at) VALUES (%s, %s, %s, %s, %s)",
                    news
                )
            print("✅ Sample news created for Comprof")
        
                # Create chat_messages table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                guest_name VARCHAR(100) NULL,
                guest_email VARCHAR(100) NULL,
                message TEXT NOT NULL,
                message_type ENUM('guest_to_admin', 'admin_to_guest', 'admin_to_user', 'user_to_admin') DEFAULT 'guest_to_admin',
                status ENUM('unread', 'read', 'replied') DEFAULT 'unread',
                parent_message_id INT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY (parent_message_id) REFERENCES chat_messages(id) ON DELETE SET NULL
            )
        ''')
        
        # Create chat_sessions table untuk tracking conversation
        cur.execute('''
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                guest_email VARCHAR(100) NULL,
                guest_name VARCHAR(100) NULL,
                status ENUM('active', 'closed', 'pending') DEFAULT 'active',
                last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        ''')
        
        conn.commit()
        cur.close()
        print("✅ Database initialized successfully!")
        
    except mysql.connector.Error as e:
        print(f"❌ Database initialization failed: {e}")
    finally:
        if conn:
            conn.close()

# ==================== EGGMONITOR DATA FUNCTIONS ====================
def build_dashboard_data():
    # --- Header ---
    header = {
        "user_name": current_user.name if current_user.is_authenticated else "Pengguna",
        "egg_vision_count": 10,
        "location": "Klari, Karawang",
        "device": "EggVision 01",
        "date_str": datetime.now().strftime("%d/%b/%Y"),
        "time_str": datetime.now().strftime("%H:%M:%S"),
        "avatar_seed": current_user.name.lower().replace(" ", "") if current_user.is_authenticated else "user"
    }

    # --- Notifications ---
    notifications = [
        {"id": "1", "message": "12 telur busuk terdeteksi pukul 08:30"},
        {"id": "2", "message": "12 telur busuk terdeteksi pukul 08:30"},
    ]

    # --- Grades / Donut chart ---
    grades = [
        {"label": "Grade I", "count": 785, "percentage": 61, "color": "#4f46e5"},
        {"label": "Grade II", "count": 342, "percentage": 27, "color": "#22c55e"},
        {"label": "Grade III", "count": 117, "percentage": 9, "color": "#f59e0b"},
        {"label": "Reject (retak/busuk)", "count": 40, "percentage": 3, "color": "#ef4444"},
    ]
    total = sum(g["count"] for g in grades)

    # Calculate donut geometry
    r = 70
    circumference = 2 * math.pi * r
    acc_pct = 0.0
    for i, g in enumerate(grades):
        g["dash"] = g["percentage"] / 100.0 * circumference
        g["gap"] = circumference - g["dash"]
        g["rotation"] = -90.0 + (acc_pct * 360.0 / 100.0)
        acc_pct += g["percentage"]

    # --- Status Panel ---
    status_items = [
        {
            "id": "eggvision", "label": "Turn On EggVision",
            "is_on": True, "variant": "success", "sub_items": []
        },
        {
            "id": "loadcell", "label": "Load Cell",
            "is_on": True, "variant": "success", "sub_items": []
        },
        {
            "id": "vision", "label": "Vision Camera",
            "is_on": False, "variant": "danger",
            "sub_items": [
                {"label": "Klasifikasi Warna", "is_on": False},
                {"label": "Pengolahan Citra", "is_on": False},
                {"label": "Estimasi Masa Simpan", "is_on": False},
            ]
        },
        {
            "id": "conveyor", "label": "Konveyor",
            "is_on": True, "variant": "default",
            "sub_items": [
                {"label": "Jalur Kanan EggVision", "is_on": True},
                {"label": "Jalur Tengah EggVision", "is_on": True},
                {"label": "Jalur Kiri EggVision", "is_on": True},
            ]
        },
    ]

    # --- Data Table ---
    records = [
        {
            "no": 1, "idNumerik": "2025101901", "tanggal": "16/Oct/2025 16:55:15",
            "ketebalan": "Sedang", "kebersihan": "Bersih", "keutuhan": "Utuh",
            "kesegaran": "Segar", "beratTelur": "50.2 gram"
        },
        {
            "no": 2, "idNumerik": "2025101902", "tanggal": "16/Oct/2025 16:54:15",
            "ketebalan": "Tipis", "kebersihan": "Bersih", "keutuhan": "Retak",
            "kesegaran": "Segar", "beratTelur": "55 gram"
        },
        {
            "no": 3, "idNumerik": "2025101903", "tanggal": "16/Oct/2025 16:53:15",
            "ketebalan": "Tebal", "kebersihan": "Cukup Bersih", "keutuhan": "Utuh",
            "kesegaran": "Segar", "beratTelur": "65 gram"
        },
        {
            "no": 4, "idNumerik": "2025101904", "tanggal": "16/Oct/2025 16:54:15",
            "ketebalan": "Tebal", "kebersihan": "Tidak Bersih", "keutuhan": "Utuh",
            "kesegaran": "Busuk", "beratTelur": "67.5 gram"
        },
        {
            "no": 5, "idNumerik": "2025101905", "tanggal": "16/Oct/2025 16:54:15",
            "ketebalan": "Tipis", "kebersihan": "Cukup Bersih", "keutuhan": "Retak",
            "kesegaran": "Busuk", "beratTelur": "55.4 gram"
        },
    ]

    return {
        "active_menu": "dashboard",
        "header": header,
        "notifications": notifications,
        "grades": grades,
        "grades_total": total,
        "donut_r": r,
        "donut_circ": circumference,
        "status_items": status_items,
        "records": records,
        "table_meta": {
            "total_records": "1,500 records",
            "rows_shown": 5
        }
    }

def build_report_data():
    header = {
        "user_name": current_user.name if current_user.is_authenticated else "Pengguna",
        "egg_vision_count": 10,
        "location": "Klari, Karawang",
        "device": "EggVision 01",
        "date_str": datetime.now().strftime("%d/%b/%Y"),
        "time_str": datetime.now().strftime("%H:%M:%S"),
        "avatar_seed": current_user.name.lower().replace(" ", "") if current_user.is_authenticated else "user"
    }

    # Data tabel
    records = [
        {"no":1,"idNumerik":"2025101901","tanggal":"16/Oct/2025 16:55:15","ketebalan":"Sedang","kebersihan":"Bersih","keutuhan":"Utuh","kesegaran":"Segar","beratTelur":"50.2 gram","kategori":"Grade III","parameter":"Tidak Cacat","keterangan":"Sempurna"},
        {"no":2,"idNumerik":"2025101902","tanggal":"16/Oct/2025 16:54:15","ketebalan":"Tipis","kebersihan":"Bersih","keutuhan":"Retak","kesegaran":"Segar","beratTelur":"55 gram","kategori":"Reject","parameter":"Ketebalan","keterangan":"Kulit Terlalu Tipis"},
        {"no":3,"idNumerik":"2025101903","tanggal":"16/Oct/2025 16:53:15","ketebalan":"Tebal","kebersihan":"Cukup Bersih","keutuhan":"Utuh","kesegaran":"Segar","beratTelur":"65 gram","kategori":"Grade III","parameter":"Kebersihan","keterangan":"Noda Melebihi Batas"},
        {"no":4,"idNumerik":"2025101904","tanggal":"16/Oct/2025 16:52:15","ketebalan":"Tebal","kebersihan":"Tidak Bersih","keutuhan":"Utuh","kesegaran":"Busuk","beratTelur":"67.5 gram","kategori":"Grade III","parameter":"Ketebalan","keterangan":"Berat Sedang"},
        {"no":5,"idNumerik":"2025101905","tanggal":"16/Oct/2025 16:51:15","ketebalan":"Tipis","kebersihan":"Cukup Bersih","keutuhan":"Retak","kesegaran":"Busuk","beratTelur":"55.4 gram","kategori":"Reject","parameter":"Berat","keterangan":"Berat Kecil"},
    ]
    table_meta = {"total_records": "1,500 records", "rows_shown": 5}

    # Grafik histogram
    hist_labels = [f"S{i+1}" for i in range(12)]
    hist_values = [240, 420, 180, 260, 120, 460, 380, 210, 160, 430, 250, 360]

    # Ringkasan kategori mutu
    grade_summary = [
        {"id":"grade1", "label":"Grade I", "count":198},
        {"id":"grade2", "label":"Grade II", "count":76},
        {"id":"grade3", "label":"Grade III", "count":85},
        {"id":"reject", "label":"Reject", "count":10},
    ]
    total_butir = sum(g["count"] for g in grade_summary)
    for g in grade_summary:
        g["pct"] = 0 if total_butir == 0 else round(g["count"]*100/total_butir,1)

    return {
        "active_menu": "laporan",
        "header": header,
        "records": records,
        "table_meta": table_meta,
        "hist_labels": hist_labels,
        "hist_values": hist_values,
        "grade_summary": grade_summary,
        "total_butir": total_butir
    }

def build_user_data():
    settings_items = [
        {"icon": "key", "title": "Account", "desc": "Perbarui kredensial & info akun"},
        {"icon": "lock", "title": "Privacy", "desc": "Preferensi privasi & keamanan"},
        {"icon": "palette", "title": "Tema", "desc": "Light/Dark & warna aksen"},
        {"icon": "bell", "title": "Notifikasi", "desc": "Pengaturan pesan notifikasi"},
        {"icon": "keyboard", "title": "Pintasan Keyboard", "desc": "Navigasi cepat"},
        {"icon": "help-circle", "title": "Pusat Bantuan", "desc": "FAQ, kontak, kebijakan"},
    ]
    
    return {
        "user": {
            "name": current_user.name if current_user.is_authenticated else "Pengguna",
            "tagline": "Giving up is an not option",
            "avatar_seed": current_user.name.lower().replace(" ", "") if current_user.is_authenticated else "user",
            "phone_display": "+62 813-1777-3184",
            "phone_raw": "+6281317773184",
        },
        "settings_items": settings_items,
    }

# ==================== AUTHENTICATION ROUTES ====================
@app.route('/login', methods=['GET', 'POST'])
def auth_login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        user = User.get_by_email(email)
        
        if user and check_password_hash(user.password, password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('Email atau password salah!', 'error')
    
    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def auth_register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Check if user already exists
        existing_user = User.get_by_email(email)
        if existing_user:
            flash('Email sudah terdaftar!', 'error')
            return render_template('auth/register.html')
        
        # Create new user as Pembeli
        hashed_password = generate_password_hash(password , method='pbkdf2:sha256')
        conn = get_db_connection()
        if not conn:
            flash('Database connection error!', 'error')
            return render_template('auth/register.html')
            
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                (name, email, hashed_password, 'pembeli')
            )
            conn.commit()
            cur.close()
            
            # Get the new user and log them in
            new_user = User.get_by_email(email)
            if new_user:
                login_user(new_user)
                flash('Registrasi berhasil! Selamat datang di EggVision.', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Error creating user account.', 'error')
                
        except mysql.connector.Error as e:
            flash('Database error during registration.', 'error')
            print(f"Registration error: {e}")
        finally:
            if conn:
                conn.close()
    
    return render_template('auth/register.html')

@app.route('/logout')
@login_required
def auth_logout():
    logout_user()
    flash('Anda telah logout.', 'info')
    return redirect(url_for('comprof_controller.comprof_beranda'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Redirect user to their respective dashboard based on role"""
    if current_user.role == 'admin':
        return redirect(url_for('eggmin_controller.eggmin'))
    elif current_user.role == 'pengusaha':
        return redirect(url_for('eggmonitor'))
    elif current_user.role == 'pembeli':
        return redirect(url_for('eggmart_controller.eggmart'))
    else:
        return redirect(url_for('comprof_controller.comprof_beranda'))

# ==================== COMPROF ROUTES (PUBLIC - ACCESSIBLE BY ALL) ====================
@app.route('/')
def comprof_beranda():
    """Homepage - accessible by everyone"""
    # Get published news from database for the homepage
    conn = get_db_connection()
    news_list = []
    
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM news WHERE is_published = TRUE ORDER BY published_at DESC LIMIT 10")
            news_list = cur.fetchall()
            cur.close()
        except mysql.connector.Error as e:
            print(f"Error fetching news: {e}")
        finally:
            if conn:
                conn.close()
    
    return render_template('comprof/beranda.html', news_list=news_list)

@app.route('/berita')
def comprof_berita():
    """News page - accessible by everyone"""
    # Get published news from database
    conn = get_db_connection()
    news_list = []
    
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM news WHERE is_published = TRUE ORDER BY published_at DESC LIMIT 10")
            news_list = cur.fetchall()
            cur.close()
        except mysql.connector.Error as e:
            print(f"Error fetching news: {e}")
        finally:
            if conn:
                conn.close()
    
    return render_template('comprof/berita.html', news_list=news_list)

@app.route('/layanan')
def comprof_layanan():
    """Services page - accessible by everyone"""
    return render_template('comprof/layanan.html')

@app.route('/produk')
def comprof_produk():
    """Products page - accessible by everyone"""
    return render_template('comprof/produk.html')

@app.route('/tentang-kami')
def comprof_tentang_kami():
    """About page - accessible by everyone"""
    return render_template('comprof/tentangkami.html')

@app.route('/kontak')
def comprof_kontak():
    """Contact page - accessible by everyone"""
    return render_template('comprof/kontak.html')

# ==================== EGGMART ROUTES (PEMBELI ONLY) ====================
@app.route('/eggmart-dashboard')
@login_required
def eggmartDashboard():
    return render_template('eggmart/index.html')



SELLERS = [
    {
        "id": 1,
        "code": "PS",
        "name": "Peternakan Sejahtera",
        "location": "Bogor, Jawa Barat",
        "rating": 4.9,
        "review_count": 1250,
        "products": [
            {
                "grade": "A",
                "stock": 500,
                "price": 28000,
                "description": "Telur premium dari ayam kampung organik",
            },
            {
                "grade": "B",
                "stock": 800,
                "price": 22000,
                "description": "Telur berkualitas dari ayam layer",
            },
        ],
    },
    {
        "id": 2,
        "code": "TB",
        "name": "Toko Telur Barokah",
        "location": "Malang, Jawa Timur",
        "rating": 4.8,
        "review_count": 890,
        "products": [
            {
                "grade": "A",
                "stock": 350,
                "price": 27000,
                "description": "Telur segar langsung dari peternakan",
            },
            {
                "grade": "C",
                "stock": 600,
                "price": 18000,
                "description": "Telur ekonomis untuk usaha kuliner",
            },
        ],
    },
    {
        "id": 3,
        "code": "MJ",
        "name": "CV. Maju Jaya Farm",
        "location": "Bandung, Jawa Barat",
        "rating": 4.7,
        "review_count": 654,
        "products": [
            {
                "grade": "B",
                "stock": 1000,
                "price": 23000,
                "description": "Telur berkualitas harga terjangkau",
            },
        ],
    },
]


@app.route("/catalog")
def buyer_catalog():
    # aktifin menu apa aja terserah kamu, sementara pakai "dashboard" biar gak error
    return render_template(
        "eggmart/catalog_list.html",
        sellers=SELLERS,
        active_menu="dashboard",
        now=None,  # atau datetime.now() kalau mau live
    )


@app.route("/catalog/<int:seller_id>")
def buyer_catalog_detail(seller_id):
    seller = next((s for s in SELLERS if s["id"] == seller_id), None)

    return render_template(
        "eggmart/catalog_detail.html",
        seller=seller,
        active_menu="dashboard",
        now=None,
    )
    


# ==================== EGGMONITOR ROUTES (PENGUSAHA ONLY) ====================
@app.route('/eggmonitor')
@login_required
def eggmonitor():
    """EggMonitor main dashboard - Pengusaha only"""
    if current_user.role != 'pengusaha':
        flash('Hanya Pengusaha yang dapat mengakses EggMonitor.', 'error')
        return redirect(url_for('comprof_controller.comprof_beranda'))
    
    data = build_dashboard_data()
    return render_template('eggmonitor/index.html', **data)

# EggMonitor legacy routes for existing templates
@app.route('/eggmonitor/')
@login_required
def eggmonitor_redirect():
    if current_user.role != 'pengusaha':
        flash('Hanya Pengusaha yang dapat mengakses EggMonitor.', 'error')
        return redirect(url_for('comprof_controller.comprof_beranda'))
    data = build_dashboard_data()
    return render_template('eggmonitor/index.html', **data)

@app.route('/eggmonitor/index')
@login_required
def eggmonitor_index():
    if current_user.role != 'pengusaha':
        flash('Hanya Pengusaha yang dapat mengakses EggMonitor.', 'error')
        return redirect(url_for('comprof_controller.comprof_beranda'))
    data = build_dashboard_data()
    return render_template('eggmonitor/index.html', **data)

@app.route('/eggmonitor/laporan')
@login_required
def eggmonitor_laporan():
    if current_user.role != 'pengusaha':
        flash('Hanya Pengusaha yang dapat mengakses EggMonitor.', 'error')
        return redirect(url_for('comprof_controller.comprof_beranda'))
    data = build_report_data()
    return render_template('eggmonitor/laporan.html', **data)

@app.route('/eggmonitor/profile')
@login_required
def eggmonitor_profile():
    if current_user.role != 'pengusaha':
        flash('Hanya Pengusaha yang dapat mengakses EggMonitor.', 'error')
        return redirect(url_for('comprof_controller.comprof_beranda'))
    data = build_user_data()
    return render_template('eggmonitor/profile.html', **data, active_menu="profile")

@app.route('/eggmonitor/settings')
@login_required
def eggmonitor_settings():
    if current_user.role != 'pengusaha':
        flash('Hanya Pengusaha yang dapat mengakses EggMonitor.', 'error')
        return redirect(url_for('comprof_controller.comprof_beranda'))
    data = build_user_data()
    return render_template('eggmonitor/settings.html', **data, active_menu="settings")

# ==================== CHAT ROUTES ====================
@app.route('/api/chat/send', methods=['POST'])
def comprof_send_chat():
    """Handle chat messages from Comprof pages"""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({'success': False, 'error': 'Message is required'}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        try:
            cur = conn.cursor()
            
            if data.get('user_id'):
                # User is logged in
                user_id = data['user_id']
                cur.execute(
                    "INSERT INTO chat_messages (user_id, message, message_type) VALUES (%s, %s, 'user_to_admin')",
                    (user_id, message)
                )
            else:
                # Guest user
                guest_name = data.get('guest_name', '').strip()
                guest_email = data.get('guest_email', '').strip()
                
                if not guest_name or not guest_email:
                    return jsonify({'success': False, 'error': 'Name and email are required for guests'}), 400
                
                cur.execute(
                    "INSERT INTO chat_messages (guest_name, guest_email, message, message_type) VALUES (%s, %s, %s, 'guest_to_admin')",
                    (guest_name, guest_email, message)
                )
            
            conn.commit()
            cur.close()
            
            # TODO: Send email notification to admin
            print(f"📩 New chat message received: {message}")
            
            return jsonify({'success': True, 'message': 'Message sent successfully'})
            
        except mysql.connector.Error as e:
            print(f"Database error in chat: {e}")
            return jsonify({'success': False, 'error': 'Database error'}), 500
        finally:
            if conn:
                conn.close()
                
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

# ==================== EGGMIN ROUTES (ADMIN ONLY) ====================
@app.route('/eggmin')
@login_required
def eggmin():
    """EggMin admin dashboard - Admin only"""
    if current_user.role != 'admin':
        flash('Hanya Admin yang dapat mengakses EggMin.', 'error')
        return redirect(url_for('comprof_controller.comprof_beranda'))
    
    # Get stats for admin dashboard
    conn = get_db_connection()
    stats = {}
    recent_users = []
    
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            
            # Get user counts
            cur.execute("SELECT COUNT(*) as count FROM users")
            stats['total_users'] = cur.fetchone()['count']
            
            cur.execute("SELECT COUNT(*) as count FROM users WHERE role = 'pembeli'")
            stats['pembeli_count'] = cur.fetchone()['count']
            
            cur.execute("SELECT COUNT(*) as count FROM users WHERE role = 'pengusaha'")
            stats['pengusaha_count'] = cur.fetchone()['count']
            
            cur.execute("SELECT COUNT(*) as count FROM users WHERE role = 'admin'")
            stats['admin_count'] = cur.fetchone()['count']
            
            # Get product counts
            cur.execute("SELECT COUNT(*) as count FROM products")
            stats['total_products'] = cur.fetchone()['count']
            
            # Get news counts
            cur.execute("SELECT COUNT(*) as count FROM news")
            stats['total_news'] = cur.fetchone()['count']
            
            # Get unread chat count
            cur.execute("SELECT COUNT(*) as count FROM chat_messages WHERE status = 'unread'")
            stats['unread_chats'] = cur.fetchone()['count']
            
            # Get recent users
            cur.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT 5")
            recent_users = cur.fetchall()
            
            cur.close()
        except mysql.connector.Error as e:
            print(f"Error fetching stats: {e}")
        finally:
            if conn:
                conn.close()
    
    return render_template('eggmin/index.html', 
                         stats=stats, 
                         recent_users=recent_users,
                         active_menu='dashboard',
                         now=datetime.now())

@app.route('/eggmin/users')
@login_required
def eggmin_users():
    """User management page - Admin only"""
    if current_user.role != 'admin':
        flash('Hanya Admin yang dapat mengakses halaman users.', 'error')
        return redirect(url_for('comprof_controller.comprof_beranda'))
    
    # Get all users from database
    conn = get_db_connection()
    users = []
    
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM users ORDER BY created_at DESC")
            users = cur.fetchall()
            cur.close()
        except mysql.connector.Error as e:
            print(f"Error fetching users: {e}")
        finally:
            if conn:
                conn.close()
    
    return render_template('eggmin/users.html', 
                         users=users,
                         active_menu='users',
                         now=datetime.now())

@app.route('/eggmin/news')
@login_required
def eggmin_news():
    """News management page - Admin only"""
    if current_user.role != 'admin':
        flash('Hanya Admin yang dapat mengakses halaman berita.', 'error')
        return redirect(url_for('comprof_controller.comprof_beranda'))
    
    # Get all news from database
    conn = get_db_connection()
    news_list = []
    
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM news ORDER BY created_at DESC")
            news_list = cur.fetchall()
            cur.close()
        except mysql.connector.Error as e:
            print(f"Error fetching news: {e}")
        finally:
            if conn:
                conn.close()
    
    return render_template('eggmin/news.html', 
                         news_list=news_list,
                         active_menu='news',
                         now=datetime.now())

@app.route('/eggmin/products')
@login_required
def eggmin_products():
    """Product management page - Admin only"""
    if current_user.role != 'admin':
        flash('Hanya Admin yang dapat mengakses halaman produk.', 'error')
        return redirect(url_for('comprof_controller.comprof_beranda'))
    
    # Get all products with user info
    conn = get_db_connection()
    products = []
    
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute('''
                SELECT p.*, u.name as seller_name, u.email as seller_email
                FROM products p 
                LEFT JOIN users u ON p.user_id = u.id
                ORDER BY p.created_at DESC
            ''')
            products = cur.fetchall()
            cur.close()
        except mysql.connector.Error as e:
            print(f"Error fetching products: {e}")
        finally:
            if conn:
                conn.close()
    
    return render_template('eggmin/products.html', 
                         products=products,
                         active_menu='products',
                         now=datetime.now())

@app.route('/eggmin/chats')
@login_required
def eggmin_chats():
    """Chat management page - Admin only"""
    if current_user.role != 'admin':
        flash('Hanya Admin yang dapat mengakses halaman chat.', 'error')
        return redirect(url_for('comprof_controller.comprof_beranda'))
    
    # Get all chat messages with user info
    conn = get_db_connection()
    chat_messages = []
    
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute('''
                SELECT cm.*, 
                       COALESCE(u.name, cm.guest_name) as sender_name,
                       COALESCE(u.email, cm.guest_email) as sender_email,
                       COALESCE(u.role, 'guest') as sender_role
                FROM chat_messages cm
                LEFT JOIN users u ON cm.user_id = u.id
                ORDER BY cm.created_at DESC
                LIMIT 100
            ''')
            chat_messages = cur.fetchall()
            cur.close()
        except mysql.connector.Error as e:
            print(f"Error fetching chat messages: {e}")
        finally:
            if conn:
                conn.close()
    
    return render_template('eggmin/chats.html', 
                         chat_messages=chat_messages,
                         active_menu='chats',
                         now=datetime.now())

# ==================== EGGMIN API ROUTES (ADMIN ONLY) ====================
# Users Management APIs
@app.route('/eggmin/api/users/update/<int:user_id>', methods=['POST'])
@login_required
def eggmin_api_users_update(user_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        name = request.form.get('name')
        email = request.form.get('email')
        role = request.form.get('role')
        
        if not all([name, email, role]):
            return jsonify({'success': False, 'error': 'All fields are required'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            
            # Check if user exists and not current user
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user = cur.fetchone()
            if not user:
                return jsonify({'success': False, 'error': 'User not found'}), 404
            
            # Check if email already exists for other users
            cur.execute("SELECT id FROM users WHERE email = %s AND id != %s", (email, user_id))
            if cur.fetchone():
                return jsonify({'success': False, 'error': 'Email already exists'}), 400
            
            cur.execute(
                "UPDATE users SET name = %s, email = %s, role = %s WHERE id = %s",
                (name, email, role, user_id)
            )
            conn.commit()
            cur.close()
            
            return jsonify({'success': True, 'message': 'User updated successfully'})
            
        except mysql.connector.Error as e:
            print(f"Database error in user update: {e}")
            return jsonify({'success': False, 'error': 'Database error'}), 500
        finally:
            if conn:
                conn.close()
                
    except Exception as e:
        print(f"Error in user update: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@app.route('/eggmin/api/users/toggle-status/<int:user_id>', methods=['POST'])
@login_required
def eggmin_api_users_toggle_status(user_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    # Note: In a real application, you might want to implement soft delete
    # or status field instead of direct deletion
    return jsonify({'success': False, 'error': 'User status toggle not implemented. Use delete instead.'}), 501

@app.route('/eggmin/api/users/delete/<int:user_id>', methods=['POST'])
@login_required
def eggmin_api_users_delete(user_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    # Prevent self-deletion
    if user_id == current_user.id:
        return jsonify({'success': False, 'error': 'Cannot delete your own account'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500
    
    try:
        cur = conn.cursor()
        
        # Check if user exists
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        if not cur.fetchone():
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        # In a real application, you might want to:
        # 1. Set user status to inactive instead of deleting
        # 2. Handle related data (products, orders, etc.)
        # 3. Use soft delete
        
        # For now, we'll do direct deletion (be careful!)
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        cur.close()
        
        return jsonify({'success': True, 'message': 'User deleted successfully'})
        
    except mysql.connector.Error as e:
        print(f"Database error in user delete: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500
    finally:
        if conn:
            conn.close()

# Users Management APIs - CREATE USER
@app.route('/eggmin/api/users/create', methods=['POST'])
@login_required
def eggmin_api_users_create():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        
        if not all([name, email, password, role]):
            return jsonify({'success': False, 'error': 'Semua field harus diisi'}), 400
        
        # Validate email format
        if '@' not in email:
            return jsonify({'success': False, 'error': 'Format email tidak valid'}), 400
        
        # Validate password length
        if len(password) < 6:
            return jsonify({'success': False, 'error': 'Password harus minimal 6 karakter'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            
            # Check if email already exists
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                return jsonify({'success': False, 'error': 'Email sudah terdaftar'}), 400
            
            # Hash password and create user
            hashed_password = generate_password_hash(password)
            
            cur.execute(
                "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                (name, email, hashed_password, role)
            )
            conn.commit()
            user_id = cur.lastrowid
            cur.close()
            
            return jsonify({'success': True, 'message': 'User berhasil dibuat', 'user_id': user_id})
            
        except mysql.connector.Error as e:
            print(f"Database error in user create: {e}")
            return jsonify({'success': False, 'error': 'Database error'}), 500
        finally:
            if conn:
                conn.close()
                
    except Exception as e:
        print(f"Error in user create: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

# GET USER DATA FOR EDIT
@app.route('/eggmin/api/users/<int:user_id>', methods=['GET'])
@login_required
def eggmin_api_users_get(user_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500
    
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, name, email, role, created_at FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        cur.close()
        
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        return jsonify({'success': True, 'user': user})
        
    except mysql.connector.Error as e:
        print(f"Database error in user get: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500
    finally:
        if conn:
            conn.close()

# News Management APIs
@app.route('/eggmin/api/news/create', methods=['POST'])
@login_required
def eggmin_api_news_create():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        title = request.form.get('title')
        content = request.form.get('content')
        image_url = request.form.get('image_url')
        is_published = request.form.get('is_published') == 'on'
        
        if not title or not content:
            return jsonify({'success': False, 'error': 'Title and content are required'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            published_at = datetime.now() if is_published else None
            
            cur.execute(
                "INSERT INTO news (title, content, image_url, is_published, published_at) VALUES (%s, %s, %s, %s, %s)",
                (title, content, image_url, is_published, published_at)
            )
            conn.commit()
            news_id = cur.lastrowid
            cur.close()
            
            return jsonify({'success': True, 'message': 'News created successfully', 'news_id': news_id})
            
        except mysql.connector.Error as e:
            print(f"Database error in news create: {e}")
            return jsonify({'success': False, 'error': 'Database error'}), 500
        finally:
            if conn:
                conn.close()
                
    except Exception as e:
        print(f"Error in news create: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

# ==================== EGGMIN NEWS API ROUTES ====================

# GET NEWS DATA FOR EDIT
@app.route('/eggmin/api/news/<int:news_id>', methods=['GET'])
@login_required
def eggmin_api_news_get(news_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500
    
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM news WHERE id = %s", (news_id,))
        news = cur.fetchone()
        cur.close()
        
        if not news:
            return jsonify({'success': False, 'error': 'News not found'}), 404
        
        # Convert datetime to string for JSON serialization
        if news['published_at']:
            news['published_at'] = news['published_at'].strftime('%Y-%m-%d %H:%M:%S')
        if news['created_at']:
            news['created_at'] = news['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            
        return jsonify({'success': True, 'news': news})
        
    except mysql.connector.Error as e:
        print(f"Database error in news get: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500
    finally:
        if conn:
            conn.close()

# UPDATE NEWS
@app.route('/eggmin/api/news/update/<int:news_id>', methods=['POST'])
@login_required
def eggmin_api_news_update(news_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        title = request.form.get('title')
        content = request.form.get('content')
        image_url = request.form.get('image_url')
        is_published = request.form.get('is_published') == 'on'
        
        if not title or not content:
            return jsonify({'success': False, 'error': 'Judul dan konten berita harus diisi'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            
            # Check if news exists
            cur.execute("SELECT * FROM news WHERE id = %s", (news_id,))
            if not cur.fetchone():
                return jsonify({'success': False, 'error': 'Berita tidak ditemukan'}), 404
            
            # Get current published status
            cur.execute("SELECT is_published, published_at FROM news WHERE id = %s", (news_id,))
            current_data = cur.fetchone()
            current_status = current_data[0]
            current_published_at = current_data[1]
            
            published_at = current_published_at
            if is_published and not current_status:
                # If changing from draft to published, set published_at to now
                published_at = datetime.now()
            elif not is_published:
                # If unpublishing, set published_at to None
                published_at = None
            
            cur.execute(
                "UPDATE news SET title = %s, content = %s, image_url = %s, is_published = %s, published_at = %s WHERE id = %s",
                (title, content, image_url, is_published, published_at, news_id)
            )
                
            conn.commit()
            cur.close()
            
            return jsonify({'success': True, 'message': 'Berita berhasil diperbarui'})
            
        except mysql.connector.Error as e:
            print(f"Database error in news update: {e}")
            return jsonify({'success': False, 'error': 'Database error'}), 500
        finally:
            if conn:
                conn.close()
                
    except Exception as e:
        print(f"Error in news update: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

# TOGGLE PUBLISH STATUS
@app.route('/eggmin/api/news/toggle-publish/<int:news_id>', methods=['POST'])
@login_required
def eggmin_api_news_toggle_publish(news_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Get current status
        cur.execute("SELECT is_published FROM news WHERE id = %s", (news_id,))
        result = cur.fetchone()
        if not result:
            return jsonify({'success': False, 'error': 'Berita tidak ditemukan'}), 404
        
        current_status = result['is_published']
        new_status = not current_status
        published_at = datetime.now() if new_status else None
        
        cur.execute(
            "UPDATE news SET is_published = %s, published_at = %s WHERE id = %s",
            (new_status, published_at, news_id)
        )
            
        conn.commit()
        cur.close()
        
        action = "dipublikasikan" if new_status else "disimpan sebagai draft"
        return jsonify({'success': True, 'message': f'Berita berhasil {action}', 'new_status': new_status})
        
    except mysql.connector.Error as e:
        print(f"Database error in news toggle: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500
    finally:
        if conn:
            conn.close()

# DELETE NEWS
@app.route('/eggmin/api/news/delete/<int:news_id>', methods=['POST'])
@login_required
def eggmin_api_news_delete(news_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500
    
    try:
        cur = conn.cursor()
        
        # Check if news exists
        cur.execute("SELECT * FROM news WHERE id = %s", (news_id,))
        if not cur.fetchone():
            return jsonify({'success': False, 'error': 'Berita tidak ditemukan'}), 404
        
        cur.execute("DELETE FROM news WHERE id = %s", (news_id,))
        conn.commit()
        cur.close()
        
        return jsonify({'success': True, 'message': 'Berita berhasil dihapus'})
        
    except mysql.connector.Error as e:
        print(f"Database error in news delete: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500
    finally:
        if conn:
            conn.close()

# Chats Management APIs
@app.route('/eggmin/api/chats/reply/<int:chat_id>', methods=['POST'])
@login_required
def eggmin_api_chats_reply(chat_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        message = request.form.get('message', '').strip()
        
        if not message:
            return jsonify({'success': False, 'error': 'Message is required'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            
            # Get original message details
            cur.execute('''
                SELECT user_id, guest_email, guest_name, message_type 
                FROM chat_messages 
                WHERE id = %s
            ''', (chat_id,))
            original_msg = cur.fetchone()
            
            if not original_msg:
                return jsonify({'success': False, 'error': 'Original message not found'}), 404
            
            # Determine reply type and recipient
            if original_msg[0]:  # user_id exists (registered user)
                reply_type = 'admin_to_user'
                user_id = original_msg[0]
                guest_email = None
                guest_name = None
            else:  # guest user
                reply_type = 'admin_to_guest'
                user_id = None
                guest_email = original_msg[1]
                guest_name = original_msg[2]
            
            # Insert reply message
            cur.execute('''
                INSERT INTO chat_messages 
                (user_id, guest_name, guest_email, message, message_type, parent_message_id, status) 
                VALUES (%s, %s, %s, %s, %s, %s, 'read')
            ''', (user_id, guest_name, guest_email, message, reply_type, chat_id))
            
            # Update original message status to replied
            cur.execute('''
                UPDATE chat_messages 
                SET status = 'replied' 
                WHERE id = %s
            ''', (chat_id,))
            
            conn.commit()
            cur.close()
            
            # TODO: Send email notification to the user/guest
            print(f"📩 Admin replied to chat {chat_id}: {message}")
            
            return jsonify({'success': True, 'message': 'Reply sent successfully'})
            
        except mysql.connector.Error as e:
            print(f"Database error in chat reply: {e}")
            return jsonify({'success': False, 'error': 'Database error'}), 500
        finally:
            if conn:
                conn.close()
                
    except Exception as e:
        print(f"Error in chat reply: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@app.route('/eggmin/api/chats/mark-read/<int:chat_id>', methods=['POST'])
@login_required
def eggmin_api_chats_mark_read(chat_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500
    
    try:
        cur = conn.cursor()
        
        # Check if message exists
        cur.execute("SELECT * FROM chat_messages WHERE id = %s", (chat_id,))
        if not cur.fetchone():
            return jsonify({'success': False, 'error': 'Message not found'}), 404
        
        cur.execute(
            "UPDATE chat_messages SET status = 'read' WHERE id = %s",
            (chat_id,)
        )
        conn.commit()
        cur.close()
        
        return jsonify({'success': True, 'message': 'Message marked as read'})
        
    except mysql.connector.Error as e:
        print(f"Database error in mark read: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500
    finally:
        if conn:
            conn.close()

@app.route('/eggmin/api/chats/delete/<int:chat_id>', methods=['POST'])
@login_required
def eggmin_api_chats_delete(chat_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500
    
    try:
        cur = conn.cursor()
        
        # Check if message exists
        cur.execute("SELECT * FROM chat_messages WHERE id = %s", (chat_id,))
        if not cur.fetchone():
            return jsonify({'success': False, 'error': 'Message not found'}), 404
        
        cur.execute("DELETE FROM chat_messages WHERE id = %s", (chat_id,))
        conn.commit()
        cur.close()
        
        return jsonify({'success': True, 'message': 'Message deleted successfully'})
        
    except mysql.connector.Error as e:
        print(f"Database error in chat delete: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500
    finally:
        if conn:
            conn.close()

# Initialize database when app starts
with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5001)