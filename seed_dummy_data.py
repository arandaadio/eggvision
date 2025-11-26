import mysql.connector
import random
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from utils.database import get_db_connection

def seed_data():
    print("🌱 Memulai seeding data dummy untuk EggMart & EggMonitor...")
    
    conn = get_db_connection()
    if not conn:
        print("❌ Gagal koneksi database")
        return

    try:
        cur = conn.cursor()

        # ==========================================
        # 1. DATA PENGUSAHA (SELLERS)
        # ==========================================
        print("creating sellers...")
        
        sellers_data = [
            {
                "name": "Berkah Farm Blitar",
                "email": "berkah@eggvision.com",
                "location": "Blitar, Jawa Timur",
                "desc": "Pusat telur grosir termurah langsung dari kandang. Melayani partai besar.",
                "code": "BF",
                "quality_profile": "bulk" # Banyak stok, kualitas campur
            },
            {
                "name": "Sunrise Organics Bali",
                "email": "sunrise@eggvision.com",
                "location": "Tabanan, Bali",
                "desc": "Telur ayam kampung organik, bebas antibiotik, kuning telur oranye pekat.",
                "code": "SO",
                "quality_profile": "premium" # Sedikit stok, kualitas tinggi (Grade A)
            },
            {
                "name": "Maju Jaya Egg",
                "email": "majujaya@eggvision.com",
                "location": "Lampung Selatan",
                "desc": "Distributor telur layer terpercaya sejak 2010. Kualitas stabil.",
                "code": "MJ",
                "quality_profile": "standard" # Rata-rata
            },
            {
                "name": "Cisarua Mountain Farm",
                "email": "cisarua@eggvision.com",
                "location": "Cisarua, Jawa Barat",
                "desc": "Telur segar dari dataran tinggi. Fresh setiap pagi.",
                "code": "CM",
                "quality_profile": "fresh" # Banyak Grade A & B
            }
        ]

        created_seller_ids = []

        for s in sellers_data:
            # Cek email dulu biar ga duplikat error
            cur.execute("SELECT id FROM users WHERE email = %s", (s['email'],))
            existing = cur.fetchone()
            
            if existing:
                print(f"   User {s['name']} sudah ada, skip create user.")
                created_seller_ids.append((existing[0], s['quality_profile']))
            else:
                pwd = generate_password_hash('123456')
                cur.execute('''
                    INSERT INTO users (name, email, password, role, farm_name, farm_code, farm_location, farm_description)
                    VALUES (%s, %s, %s, 'pengusaha', %s, %s, %s, %s)
                ''', (s['name'], s['email'], pwd, s['name'], s['code'], s['location'], s['desc']))
                created_seller_ids.append((cur.lastrowid, s['quality_profile']))
                print(f"   ✅ Created seller: {s['name']}")

        conn.commit()

        # ==========================================
        # 2. DATA EGG SCAN (Untuk EggMonitor & Stok)
        # ==========================================
        print("\n🥚 Generating Egg Scans (Historical Data)...")
        
        # Konfigurasi probabilitas grade berdasarkan profil toko
        profiles = {
            "premium":  {"A": 0.80, "B": 0.15, "C": 0.05, "price_mod": 1.5}, # Mahal, bagus
            "bulk":     {"A": 0.40, "B": 0.40, "C": 0.20, "price_mod": 0.8}, # Murah, campur
            "standard": {"A": 0.60, "B": 0.30, "C": 0.10, "price_mod": 1.0}, # Standar
            "fresh":    {"A": 0.70, "B": 0.25, "C": 0.05, "price_mod": 1.2}  # Agak mahal
        }

        base_prices = {"A": 28000, "B": 24000, "C": 18000} # Harga per kg (asumsi) / atau per tray, kita anggap per butir x 1000
        # Biar gampang, kita set harga per butir: A=2000, B=1800, C=1500

        for user_id, profile_type in created_seller_ids:
            prof = profiles[profile_type]
            
            # Generate data mundur 30 hari ke belakang
            for day_offset in range(30): 
                scan_date = datetime.now() - timedelta(days=day_offset)
                
                # Jumlah scan per hari (acak antara 5 sampai 15 butir per hari utk sampel)
                daily_scans = random.randint(5, 15)
                
                for _ in range(daily_scans):
                    # Tentukan Grade berdasarkan probabilitas profile
                    rand_val = random.random()
                    if rand_val < prof["A"]:
                        grade = "A"
                        weight = random.uniform(60.0, 70.0)
                        kebersihan = "Bersih"
                        keutuhan = "Utuh"
                    elif rand_val < prof["A"] + prof["B"]:
                        grade = "B"
                        weight = random.uniform(50.0, 59.9)
                        kebersihan = random.choice(["Sedikit Kotor", "Bersih"])
                        keutuhan = "Utuh"
                    else:
                        grade = "C"
                        weight = random.uniform(40.0, 49.9)
                        kebersihan = "Kotor"
                        keutuhan = random.choice(["Retak Halus", "Utuh"])

                    # Tentukan status (sold, available, listed)
                    # Data lama cenderung 'sold', data baru 'available'/'listed'
                    if day_offset > 7:
                        status = 'sold'
                        is_listed = False
                    else:
                        status = random.choice(['available', 'listed'])
                        is_listed = (status == 'listed')

                    # Harga listing (jika listed)
                    price = int((base_prices[grade] / 14.0) * prof['price_mod']) # estimasi harga per butir
                    
                    cur.execute('''
                        INSERT INTO egg_scans 
                        (user_id, numeric_id, scanned_at, ketebalan, kebersihan, keutuhan, kesegaran, berat_telur, grade, confidence, status, is_listed, listed_price)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ''', (
                        user_id, 
                        f"SCAN-{random.randint(1000,9999)}",
                        scan_date,
                        f"{random.uniform(0.3, 0.4):.2f}mm",
                        kebersihan,
                        keutuhan,
                        "Segar",
                        weight,
                        grade,
                        random.uniform(85.0, 99.9),
                        status,
                        is_listed,
                        price if is_listed else 0
                    ))
            
            print(f"   ✅ Generated scans for User ID {user_id} ({profile_type})")

        conn.commit()

        # ==========================================
        # 3. EGG LISTINGS (Stok di Marketplace)
        # ==========================================
        print("\n🛒 Updating EggMart Listings...")
        
        for user_id, profile_type in created_seller_ids:
            prof = profiles[profile_type]
            
            # Update stok Grade A
            price_a = int(2500 * prof['price_mod'])
            cur.execute('''
                INSERT INTO egg_listings (seller_id, grade, stock_eggs, price_per_egg, status)
                VALUES (%s, 'A', %s, %s, 'active')
                ON DUPLICATE KEY UPDATE stock_eggs = VALUES(stock_eggs), price_per_egg = VALUES(price_per_egg)
            ''', (user_id, random.randint(50, 500), price_a))

            # Update stok Grade B
            price_b = int(2000 * prof['price_mod'])
            cur.execute('''
                INSERT INTO egg_listings (seller_id, grade, stock_eggs, price_per_egg, status)
                VALUES (%s, 'B', %s, %s, 'active')
                ON DUPLICATE KEY UPDATE stock_eggs = VALUES(stock_eggs), price_per_egg = VALUES(price_per_egg)
            ''', (user_id, random.randint(100, 800), price_b))
            
            # Kadang ada Grade C, kadang tidak
            if profile_type != 'premium':
                price_c = int(1500 * prof['price_mod'])
                cur.execute('''
                    INSERT INTO egg_listings (seller_id, grade, stock_eggs, price_per_egg, status)
                    VALUES (%s, 'C', %s, %s, 'active')
                    ON DUPLICATE KEY UPDATE stock_eggs = VALUES(stock_eggs), price_per_egg = VALUES(price_per_egg)
                ''', (user_id, random.randint(50, 200), price_c))
                
        conn.commit()
        print("   ✅ Listings updated.")

        # ==========================================
        # 4. REVIEWS (Biar toko kelihatan hidup)
        # ==========================================
        print("\n⭐ Generating Reviews...")
        
        reviews = [
            (5, "Telurnya bersih banget, pengiriman aman!"),
            (5, "Langganan tiap minggu, gapernah kecewa."),
            (4, "Pengiriman agak lama tapi barang bagus."),
            (4, "Sesuai deskripsi, grade A nya beneran gede."),
            (5, "Mantap, kuning telurnya bagus buat bikin kue."),
            (3, "Ada 1 yang retak, tapi sisanya oke."),
            (5, "Seller ramah, respon cepat.")
        ]
        
        for user_id, _ in created_seller_ids:
            # Beri 3-5 review acak per seller
            num_reviews = random.randint(3, 5)
            for _ in range(num_reviews):
                rating, text = random.choice(reviews)
                cur.execute('''
                    INSERT INTO seller_ratings (seller_id, buyer_name, rating, review)
                    VALUES (%s, %s, %s, %s)
                ''', (user_id, "Customer EggMart", rating, text))
        
        conn.commit()
        print("   ✅ Reviews generated.")

        print("\n🎉 SEEDING COMPLETE! Database siap digunakan.")

    except mysql.connector.Error as e:
        print(f"❌ Error saat seeding: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    seed_data()