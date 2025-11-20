import mysql.connector
from werkzeug.security import generate_password_hash
from config import DB_CONFIG

def get_db_connection():
    """Get MySQL database connection"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as e:
        print(f"Database connection error: {e}")
        return None


def init_db():
    """Initialize database with required tables and data"""
    conn = get_db_connection()
    if not conn:
        print("❌ Failed to connect to database")
        return

    try:
        cur = conn.cursor()

        # ==========================
        # 1. USERS (1 user = 1 farm)
        # ==========================
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                role ENUM('guest','pembeli','pengusaha','admin') DEFAULT 'guest',

                -- Info farm (dipakai kalau role = 'pengusaha')
                farm_name VARCHAR(255) NULL,
                farm_code VARCHAR(10) NULL,
                farm_location VARCHAR(255) NULL,
                farm_description TEXT NULL,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # =========================================
        # 2. EGG_SCANS (hasil upload & prediksi ML)
        #    Sumber stok EggMart + histori EggMonitor
        # =========================================
        cur.execute('''
            CREATE TABLE IF NOT EXISTS egg_scans (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,

                numeric_id VARCHAR(50),
                scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                ketebalan VARCHAR(50),
                kebersihan VARCHAR(50),
                keutuhan VARCHAR(50),
                kesegaran VARCHAR(50),
                berat_telur DECIMAL(6,2),

                grade ENUM('A','B','C') NOT NULL,
                confidence DECIMAL(5,2),

                image_path VARCHAR(500),

                kategori VARCHAR(50),
                parameter_minus VARCHAR(100),
                keterangan TEXT,

                status ENUM('available','listed','sold','discarded')
                    DEFAULT 'available',

                is_listed BOOLEAN DEFAULT FALSE,
                listed_price DECIMAL(10,2),
                listed_at TIMESTAMP NULL,

                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
                # =====================================
        # 2b. EGG_LISTINGS (stok siap jual per grade per seller)
        # =====================================
        cur.execute('''
            CREATE TABLE IF NOT EXISTS egg_listings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                seller_id INT NOT NULL,
                grade ENUM('A','B','C') NOT NULL,
                stock_eggs INT NOT NULL DEFAULT 0,
                price_per_egg DECIMAL(10,2) NOT NULL,
                status ENUM('active','inactive') DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NULL,
                UNIQUE KEY uniq_seller_grade (seller_id, grade),
                FOREIGN KEY (seller_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')


        # =====================================
        # 3. ORDERS (Transaksi, sinkron Midtrans)
        # =====================================
        cur.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INT AUTO_INCREMENT PRIMARY KEY,

                buyer_id INT NULL,
                seller_id INT NULL,

                total DECIMAL(10,2) NOT NULL,

                midtrans_order_id VARCHAR(100),
                midtrans_transaction_id VARCHAR(100),

                status ENUM('pending','paid','settlement',
                            'cancelled','expired','refunded')
                    DEFAULT 'pending',

                payment_type VARCHAR(50),
                shipping_address TEXT,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NULL,

                UNIQUE KEY uniq_midtrans_order (midtrans_order_id),

                FOREIGN KEY (buyer_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY (seller_id) REFERENCES users(id) ON DELETE SET NULL
            )
        ''')

        # =========================================
        # 4. ORDER_ITEMS (Telur mana saja yang terjual)
        # =========================================
        cur.execute('''
            CREATE TABLE IF NOT EXISTS order_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                order_id INT NOT NULL,
                egg_scan_id INT NOT NULL,

                price DECIMAL(10,2) NOT NULL,
                quantity INT NOT NULL DEFAULT 1,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                FOREIGN KEY (egg_scan_id) REFERENCES egg_scans(id) ON DELETE RESTRICT
            )
        ''')

        # =====================================
        # 5. SELLER_RATINGS (rating & review)
        # =====================================
        cur.execute('''
            CREATE TABLE IF NOT EXISTS seller_ratings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                seller_id INT NOT NULL,
                buyer_id INT NULL,
                order_id INT NULL,

                rating TINYINT NOT NULL,
                review TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (seller_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (buyer_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL
            )
        ''')

        # ==========================
        # 6. NEWS (opsional)
        # ==========================
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

        # ==========================
        # 7. CHAT_SESSIONS
        # ==========================
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

               # ==========================
        # 8. CHAT_MESSAGES
        # ==========================
        cur.execute('''
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                session_id INT NOT NULL,
                user_id INT NULL,
                guest_name VARCHAR(100) NULL,
                guest_email VARCHAR(100) NULL,
                message TEXT NOT NULL,
                message_type ENUM(
                    'guest_to_admin',
                    'admin_to_guest',
                    'admin_to_user',
                    'user_to_admin'
                ) DEFAULT 'guest_to_admin',
                status ENUM('unread', 'read', 'replied') DEFAULT 'unread',
                parent_message_id INT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY (parent_message_id) REFERENCES chat_messages(id) ON DELETE SET NULL
            )
        ''')


        # ===========================================
        # 9. SEED DATA AWAL (admin, 1 pengusaha, 1 pembeli)
        # ===========================================
        cur.execute("SELECT COUNT(*) FROM users")
        user_count = cur.fetchone()[0]

        if user_count == 0:
            # Admin
            admin_pwd = generate_password_hash('admin123', method='pbkdf2:sha256')
            cur.execute(
                "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                ('Admin EggMin', 'admin@eggvision.test', admin_pwd, 'admin')
            )

            # Pengusaha (punya farm)
            seller_pwd = generate_password_hash('seller123', method='pbkdf2:sha256')
            cur.execute(
                '''
                INSERT INTO users
                    (name, email, password, role,
                     farm_name, farm_code, farm_location, farm_description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ''',
                (
                    'Peternakan Sejahtera',
                    'seller@eggvision.test',
                    seller_pwd,
                    'pengusaha',
                    'Peternakan Sejahtera',
                    'PS',
                    'Bogor, Jawa Barat',
                    'Telur ayam kampung & layer berkualitas.'
                )
            )

            # Pembeli contoh
            buyer_pwd = generate_password_hash('buyer123', method='pbkdf2:sha256')
            cur.execute(
                "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                ('Pembeli Contoh', 'buyer@eggvision.test', buyer_pwd, 'pembeli')
            )

        conn.commit()
        cur.close()
        print("✅ Database initialized successfully!")

    except mysql.connector.Error as e:
        print(f"❌ Database initialization failed: {e}")
    finally:
        if conn:
            conn.close()
