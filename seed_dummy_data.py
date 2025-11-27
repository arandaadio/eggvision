import mysql.connector
import random
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from utils.database import get_db_connection

# Password default untuk semua user
DEFAULT_PASSWORD = "123456"

def seed_data():
    print("🌱 Memulai seeding data dummy v2 (Sinkronisasi Listing)...")
    
    conn = get_db_connection()
    if not conn:
        print("❌ Gagal koneksi database")
        return

    try:
        cur = conn.cursor()

        # ==========================================
        # 1. DATA PENGUSAHA (6 TOKO BERAGAM)
        # ==========================================
        print("creating sellers...")
        
        sellers_data = [
            {
                "name": "Berkah Farm Blitar",
                "email": "berkah@eggvision.com",
                "location": "Blitar, Jawa Timur",
                "desc": "Pusat telur grosir termurah langsung dari kandang. Melayani partai besar.",
                "code": "BF",
                "quality_profile": "bulk"  # Banyak stok, murah, kualitas campur
            },
            {
                "name": "Sunrise Organics Bali",
                "email": "sunrise@eggvision.com",
                "location": "Tabanan, Bali",
                "desc": "Telur ayam kampung organik, bebas antibiotik, kuning telur oranye pekat.",
                "code": "SO",
                "quality_profile": "premium" # Sedikit stok, mahal, Grade A dominan
            },
            {
                "name": "Maju Jaya Egg",
                "email": "majujaya@eggvision.com",
                "location": "Lampung Selatan",
                "desc": "Distributor telur layer terpercaya sejak 2010. Kualitas stabil.",
                "code": "MJ",
                "quality_profile": "standard" 
            },
            {
                "name": "Cisarua Mountain Farm",
                "email": "cisarua@eggvision.com",
                "location": "Cisarua, Jawa Barat",
                "desc": "Telur segar dari dataran tinggi. Fresh setiap pagi.",
                "code": "CM",
                "quality_profile": "fresh"
            },
            {
                "name": "Jogja Telur Mandiri",
                "email": "jogja@eggvision.com",
                "location": "Sleman, Yogyakarta",
                "desc": "Telur ayam ras petelur, kuning kemerahan, cangkang tebal.",
                "code": "JT",
                "quality_profile": "standard"
            },
            {
                "name": "Borneo Egg Center",
                "email": "borneo@eggvision.com",
                "location": "Banjarbaru, Kalimantan Selatan",
                "desc": "Suplier telur terbesar di Kalimantan Selatan. Stok selalu ready.",
                "code": "BE",
                "quality_profile": "bulk"
            }
        ]

        created_seller_ids = []

        pwd_hash = generate_password_hash(DEFAULT_PASSWORD)

        for s in sellers_data:
            # Cek email dulu biar ga duplikat error
            cur.execute("SELECT id FROM users WHERE email = %s", (s['email'],))
            existing = cur.fetchone()
            
            if existing:
                print(f"   User {s['name']} sudah ada, menggunakan ID lama.")
                created_seller_ids.append((existing[0], s['quality_profile']))
            else:
                cur.execute('''
                    INSERT INTO users (name, email, password, role, farm_name, farm_code, farm_location, farm_description)
                    VALUES (%s, %s, %s, 'pengusaha', %s, %s, %s, %s)
                ''', (s['name'], s['email'], pwd_hash, s['name'], s['code'], s['location'], s['desc']))
                created_seller_ids.append((cur.lastrowid, s['quality_profile']))
                print(f"   ✅ Created seller: {s['name']}")

        conn.commit()

        # ==========================================
        # 2. GENERATE EGG SCANS & SINKRONISASI LISTING
        # ==========================================
        print("\n🥚 Generating Egg Scans & Syncing Listings...")
        
        # Profil probabilitas & harga
        profiles = {
            "premium":  {"A": 0.90, "B": 0.10, "C": 0.00, "price_mod": 1.5, "daily_qty": (10, 20)}, 
            "bulk":     {"A": 0.30, "B": 0.50, "C": 0.20, "price_mod": 0.8, "daily_qty": (50, 100)}, 
            "standard": {"A": 0.60, "B": 0.30, "C": 0.10, "price_mod": 1.0, "daily_qty": (30, 60)}, 
            "fresh":    {"A": 0.70, "B": 0.25, "C": 0.05, "price_mod": 1.2, "daily_qty": (20, 40)}  
        }

        base_prices = {"A": 2500, "B": 2200, "C": 1800}

        for user_id, profile_type in created_seller_ids:
            prof = profiles[profile_type]
            
            # Dictionary untuk menghitung stok listing per grade
            listing_counts = {"A": 0, "B": 0, "C": 0}
            listing_prices = {
                "A": int(base_prices["A"] * prof['price_mod']),
                "B": int(base_prices["B"] * prof['price_mod']),
                "C": int(base_prices["C"] * prof['price_mod'])
            }

            # Generate data mundur 15 hari ke belakang
            for day_offset in range(15): 
                scan_date = datetime.now() - timedelta(days=day_offset)
                
                # Jumlah scan per hari
                daily_min, daily_max = prof["daily_qty"]
                daily_scans = random.randint(daily_min, daily_max)
                
                batch_values = []
                
                for _ in range(daily_scans):
                    # Tentukan Grade
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

                    # Tentukan status:
                    # - 60% Listed (Siap Jual di EggMart) -> Masuk perhitungan stok
                    # - 20% Sold (Sudah laku offline/transaksi lama)
                    # - 20% Available (Baru discan di EggMonitor, belum dilisting)
                    
                    status_rand = random.random()
                    is_listed = False
                    listed_price = 0
                    status = 'available'

                    if status_rand < 0.6:
                        status = 'listed'
                        is_listed = True
                        listed_price = listing_prices[grade]
                        listing_counts[grade] += 1  # Tambah stok listing
                    elif status_rand < 0.8:
                        status = 'sold'
                    else:
                        status = 'available'

                    # Masukkan ke batch
                    batch_values.append((
                        user_id, 
                        f"SCAN-{random.randint(10000,99999)}",
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
                        listed_price
                    ))

                # Bulk Insert per hari
                if batch_values:
                    cur.executemany('''
                        INSERT INTO egg_scans 
                        (user_id, numeric_id, scanned_at, ketebalan, kebersihan, keutuhan, kesegaran, berat_telur, grade, confidence, status, is_listed, listed_price)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ''', batch_values)
            
            # --- UPDATE EGG_LISTINGS SESUAI REAL COUNT DARI EGG_SCANS ---
            # Ini kunci agar validasi 'create_transaction' berhasil
            for grade in ["A", "B", "C"]:
                stock = listing_counts[grade]
                price = listing_prices[grade]
                
                # Jika stok ada, buat listing active. Jika 0, inactive/ga dibuat
                if stock > 0:
                    cur.execute('''
                        INSERT INTO egg_listings (seller_id, grade, stock_eggs, price_per_egg, status)
                        VALUES (%s, %s, %s, %s, 'active')
                        ON DUPLICATE KEY UPDATE 
                            stock_eggs = VALUES(stock_eggs), 
                            price_per_egg = VALUES(price_per_egg),
                            status = 'active'
                    ''', (user_id, grade, stock, price))
                else:
                    # Pastikan kalau stok 0, status inactive (opsional)
                    cur.execute('''
                        UPDATE egg_listings SET status = 'inactive', stock_eggs = 0
                        WHERE seller_id = %s AND grade = %s
                    ''', (user_id, grade))
            
            print(f"   ✅ User ID {user_id} ({profile_type}): Stok A={listing_counts['A']}, B={listing_counts['B']}, C={listing_counts['C']}")

        conn.commit()

        # ==========================================
        # 3. REVIEWS 
        # ==========================================
        print("\n⭐ Generating Reviews...")
        
        reviews_pool = [
            (5, "Telurnya bersih banget, pengiriman aman!"),
            (5, "Langganan tiap minggu, gapernah kecewa."),
            (4, "Pengiriman agak lama tapi barang bagus."),
            (4, "Sesuai deskripsi, grade A nya beneran gede."),
            (5, "Mantap, kuning telurnya bagus buat bikin kue."),
            (3, "Ada 1 yang retak, tapi sisanya oke."),
            (5, "Seller ramah, respon cepat."),
            (5, "Packing kayu aman, telur utuh semua.")
        ]
        
        for user_id, _ in created_seller_ids:
            num_reviews = random.randint(3, 8)
            for _ in range(num_reviews):
                rating, text = random.choice(reviews_pool)
                # Variasi rating sedikit
                if random.random() < 0.2: rating = max(1, rating - 1)

                buyer_names = ["Budi Santoso", "Siti Aminah", "Dewi Lestari", "Agus Pratama", "Rina Wati"]
                buyer_name = random.choice(buyer_names)

                cur.execute('''
                    INSERT INTO seller_ratings (seller_id, buyer_name, rating, review)
                    VALUES (%s, %s, %s, %s)
                ''', (user_id, buyer_name, rating, text))
        
        conn.commit()
        print("   ✅ Reviews generated.")

        print("\n🎉 SEEDING COMPLETE v2! Stok fisik dan listing sudah sinkron.")
        print(f"🔑 Password untuk semua akun: {DEFAULT_PASSWORD}")

    except mysql.connector.Error as e:
        print(f"❌ Error saat seeding: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    seed_data()