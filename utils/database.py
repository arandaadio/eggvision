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
        # 3. ORDERS (UPDATED ENUM per Migration)
        # =====================================
        cur.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INT AUTO_INCREMENT PRIMARY KEY,

                buyer_id INT NULL,
                seller_id INT NULL,

                total DECIMAL(10,2) NOT NULL,

                midtrans_order_id VARCHAR(100),
                midtrans_transaction_id VARCHAR(100),

                status ENUM('pending','paid','settlement','capture',
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
                buyer_name VARCHAR(100),
                order_id INT NULL,

                rating TINYINT NOT NULL,
                review TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (seller_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (buyer_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL
            )
        ''')

        dummy_reviews = [
            (5, "Telur berkualitas bagus, pengiriman cepat. Recommended!", "Dio Aranda"),
            (5, "Telur berkualitas bagus, pengiriman sangat cepat. Terima kasih sudah amanah!", "Sarah Aninditya"),
            (1, "Grade tidak sesuai kualitasnya, penipu!", "Fauzi Luqman"),
            (1, "Toko tidak amanah. Jangan tergiur dengan harga murahnya!", "Dzaky Az-Zshahir"),
        ]

        def insert_dummy_reviews(seller_id, cur):
            for rating, review, buyer_name in dummy_reviews:
                cur.execute(
                    "INSERT INTO seller_ratings (seller_id, buyer_name, rating, review) VALUES (%s, %s, %s, %s)",
                    (seller_id, buyer_name, rating, review)
                )

        # ==========================
        # 6. NEWS (opsional)
        # ==========================
        cur.execute('''
            CREATE TABLE IF NOT EXISTS news (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                image_url VARCHAR(500),
                tags TEXT NULL,
                is_published BOOLEAN DEFAULT FALSE,
                published_at TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # ==========================
        # 7. CHAT_SESSIONS (UPDATED)
        # ==========================
        # UPDATED: Added seller_id foreign key
        cur.execute('''
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                seller_id INT NULL, 
                
                guest_email VARCHAR(100) NULL,
                guest_name VARCHAR(100) NULL,
                
                last_message TEXT,
                last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                status ENUM('active', 'closed', 'pending') DEFAULT 'active',
                
                is_pinned BOOLEAN DEFAULT FALSE,
                is_archived BOOLEAN DEFAULT FALSE,
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY (seller_id) REFERENCES users(id) ON DELETE SET NULL
            )
        ''')

        # ==========================
        # 8. CHAT_MESSAGES (UPDATED)
        # ==========================
        # UPDATED: New ENUM types
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
                    'pembeli_to_pengusaha',
                    'pengusaha_to_pembeli',
                    'pengusaha_to_admin',
                    'admin_to_pengusaha'
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
            eggmin_pwd = generate_password_hash('eggmin123', method='pbkdf2:sha256')
            cur.execute(
                "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                ('Sandbox EggMin', 'eggmin@eggvision.com', eggmin_pwd, 'admin')
            )

            # Pengusaha
            pengusaha_pwd = generate_password_hash('pengusaha123', method='pbkdf2:sha256')
            cur.execute(
                '''
                INSERT INTO users
                    (name, email, password, role,
                     farm_name, farm_code, farm_location, farm_description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ''',
                (
                    'Sandbox EggMonitor',
                    'pengusaha@eggvision.com',
                    pengusaha_pwd,
                    'pengusaha',
                    'Sandbox EggMonitor',
                    'SE',
                    'Bogor, Jawa Barat',
                    'Telur ayam konsumsi berkualitas.'
                )
            )

            seller_id = cur.lastrowid

            # Insert dummy reviews untuk pengusaha
            insert_dummy_reviews(seller_id, cur)

            # Pembeli
            pembeli_pwd = generate_password_hash('pembeli123', method='pbkdf2:sha256')
            cur.execute(
                "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                ('Sandbox EggMart', 'pembeli@eggvision.com', pembeli_pwd, 'pembeli')
            )

        # ==========================
        # SEED BERITA DUMMY
        # ==========================
        try:
            from utils.news_data import get_dummy_news_data
            
            cur.execute("SELECT COUNT(*) FROM news")
            news_count = cur.fetchone()[0]
            
            if news_count == 0:
                print("📝 Seeding dummy news data...")
                dummy_news = get_dummy_news_data()
                
                for item in dummy_news:
                    cur.execute('''
                        INSERT INTO news (title, content, image_url, tags, is_published, published_at)
                        VALUES (%s, %s, %s, %s, TRUE, %s)
                    ''', (
                        item['title'], 
                        item['content'], 
                        item['image_url'], 
                        item['tags'], 
                        item['published_at']
                    ))
        except ImportError:
            print("⚠️ utils.news_data not found, skipping news seed.")

        conn.commit()
        cur.close()
        print("✅ Database initialized successfully !")

    except mysql.connector.Error as e:
        print(f"❌ Database initialization failed: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    init_db()