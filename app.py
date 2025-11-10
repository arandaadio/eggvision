from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import math
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

# MySQL configuration
db_config = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
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
            hashed_password = generate_password_hash('eggmin123')
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
            hashed_password = generate_password_hash('pembeli123')
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
            hashed_password = generate_password_hash('pengusaha123')
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
        hashed_password = generate_password_hash(password)
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
    return redirect(url_for('comprof_beranda'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Redirect user to their respective dashboard based on role"""
    if current_user.role == 'admin':
        return redirect(url_for('eggmin'))
    elif current_user.role == 'pengusaha':
        return redirect(url_for('eggmonitor'))
    elif current_user.role == 'pembeli':
        return redirect(url_for('eggmart'))
    else:
        return redirect(url_for('comprof_beranda'))

# ==================== COMPROF ROUTES (PUBLIC - ACCESSIBLE BY ALL) ====================
@app.route('/')
def comprof_beranda():
    """Homepage - accessible by everyone"""
    return render_template('comprof/beranda.html')

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
@app.route('/eggmart')
@login_required
def eggmart():
    """EggMart main dashboard - Pembeli only"""
    if current_user.role != 'pembeli':
        flash('Hanya Pembeli yang dapat mengakses EggMart.', 'error')
        return redirect(url_for('comprof_beranda'))
    
    # Get products from database
    conn = get_db_connection()
    products = []
    
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute('''
                SELECT p.*, u.name as seller_name 
                FROM products p 
                JOIN users u ON p.user_id = u.id 
                WHERE p.is_active = TRUE AND p.stock > 0
                ORDER BY p.created_at DESC
            ''')
            products = cur.fetchall()
            cur.close()
        except mysql.connector.Error as e:
            print(f"Error fetching products: {e}")
        finally:
            if conn:
                conn.close()
    
    return render_template('eggmart/index.html', products=products)

# ==================== EGGMONITOR ROUTES (PENGUSAHA ONLY) ====================
@app.route('/eggmonitor')
@login_required
def eggmonitor():
    """EggMonitor main dashboard - Pengusaha only"""
    if current_user.role != 'pengusaha':
        flash('Hanya Pengusaha yang dapat mengakses EggMonitor.', 'error')
        return redirect(url_for('comprof_beranda'))
    
    data = build_dashboard_data()
    return render_template('eggmonitor/index.html', **data)

# EggMonitor legacy routes for existing templates
@app.route('/eggmonitor/')
@login_required
def eggmonitor_redirect():
    if current_user.role != 'pengusaha':
        flash('Hanya Pengusaha yang dapat mengakses EggMonitor.', 'error')
        return redirect(url_for('comprof_beranda'))
    data = build_dashboard_data()
    return render_template('eggmonitor/index.html', **data)

@app.route('/eggmonitor/index')
@login_required
def eggmonitor_index():
    if current_user.role != 'pengusaha':
        flash('Hanya Pengusaha yang dapat mengakses EggMonitor.', 'error')
        return redirect(url_for('comprof_beranda'))
    data = build_dashboard_data()
    return render_template('eggmonitor/index.html', **data)

@app.route('/eggmonitor/laporan')
@login_required
def eggmonitor_laporan():
    if current_user.role != 'pengusaha':
        flash('Hanya Pengusaha yang dapat mengakses EggMonitor.', 'error')
        return redirect(url_for('comprof_beranda'))
    data = build_report_data()
    return render_template('eggmonitor/laporan.html', **data)

@app.route('/eggmonitor/profile')
@login_required
def eggmonitor_profile():
    if current_user.role != 'pengusaha':
        flash('Hanya Pengusaha yang dapat mengakses EggMonitor.', 'error')
        return redirect(url_for('comprof_beranda'))
    data = build_user_data()
    return render_template('eggmonitor/profile.html', **data, active_menu="profile")

@app.route('/eggmonitor/settings')
@login_required
def eggmonitor_settings():
    if current_user.role != 'pengusaha':
        flash('Hanya Pengusaha yang dapat mengakses EggMonitor.', 'error')
        return redirect(url_for('comprof_beranda'))
    data = build_user_data()
    return render_template('eggmonitor/settings.html', **data, active_menu="settings")

# ==================== EGGMIN ROUTES (ADMIN ONLY) ====================
@app.route('/eggmin')
@login_required
def eggmin():
    """EggMin admin dashboard - Admin only"""
    if current_user.role != 'admin':
        flash('Hanya Admin yang dapat mengakses EggMin.', 'error')
        return redirect(url_for('comprof_beranda'))
    
    # Get stats for admin dashboard
    conn = get_db_connection()
    stats = {}
    
    if conn:
        try:
            cur = conn.cursor()
            
            # Get user counts
            cur.execute("SELECT COUNT(*) as count FROM users")
            stats['total_users'] = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) as count FROM users WHERE role = 'pembeli'")
            stats['pembeli_count'] = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) as count FROM users WHERE role = 'pengusaha'")
            stats['pengusaha_count'] = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) as count FROM users WHERE role = 'admin'")
            stats['admin_count'] = cur.fetchone()[0]
            
            # Get product counts
            cur.execute("SELECT COUNT(*) as count FROM products")
            stats['total_products'] = cur.fetchone()[0]
            
            # Get news counts
            cur.execute("SELECT COUNT(*) as count FROM news")
            stats['total_news'] = cur.fetchone()[0]
            
            cur.close()
        except mysql.connector.Error as e:
            print(f"Error fetching stats: {e}")
        finally:
            if conn:
                conn.close()
    
    return render_template('eggmin/index.html', stats=stats)

# Initialize database when app starts
with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)