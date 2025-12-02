from flask import Blueprint, render_template, flash, redirect, url_for, request, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import mysql.connector
import time
import base64
import requests
from utils.db import get_db_connection
import midtransclient

eggmart_controller = Blueprint('eggmart_controller', __name__)

def get_midtrans_snap():
    print("Midtrans config:", {
        "is_production": current_app.config.get("MIDTRANS_IS_PRODUCTION", False),
        "server_key": current_app.config.get("MIDTRANS_SERVER_KEY"),
        "client_key": current_app.config.get("MIDTRANS_CLIENT_KEY"),
    }
    )
    return midtransclient.Snap(
        is_production=False,
        server_key=current_app.config.get("MIDTRANS_SERVER_KEY"),
        client_key=current_app.config.get("MIDTRANS_CLIENT_KEY"),
    )


@eggmart_controller.route('/eggmart/listing/save', methods=['POST'])
@login_required
def save_listing():
    # Optional: batasi hanya pengusaha
    # if current_user.role != 'pengusaha':
    #     flash('Hanya pengusaha yang dapat mengelola listing.', 'error')
    #     return redirect(url_for('eggmart_controller.eggmartDashboard'))

    grade = request.form.get('grade')
    price = request.form.get('price', type=float)
    stock = request.form.get('stock', type=int)

    if not grade or price is None or stock is None:
        flash('Grade, harga, dan stok wajib diisi.', 'error')
        return redirect(url_for('eggmonitor_controller.eggmonitor_seller'))

    conn = get_db_connection()
    if not conn:
        flash('Gagal terhubung ke database.', 'error')
        return redirect(url_for('eggmonitor_controller.eggmonitor_seller'))

    try:
        cur = conn.cursor(dictionary=True)

        seller_id = current_user.id

        # ==========================
        # 0) Cek listing grade ini sudah ada atau belum
        # ==========================
        cur.execute("""
            SELECT price_per_egg
            FROM egg_listings
            WHERE seller_id = %s AND grade = %s AND status = 'active'
            LIMIT 1
        """, (seller_id, grade))
        existing_listing = cur.fetchone()
        existing_price = float(existing_listing['price_per_egg']) if existing_listing else None

        # ==========================
        # 1) Ambil ID telur yang masih available untuk grade tersebut
        # ==========================
        cur.execute("""
            SELECT id
            FROM egg_scans
            WHERE user_id = %s
              AND grade = %s
              AND status = 'available'
              AND (is_listed = FALSE OR is_listed IS NULL)
            ORDER BY scanned_at ASC
            LIMIT %s
        """, (seller_id, grade, stock))
        eggs = cur.fetchall()

        if len(eggs) < stock:
            conn.rollback()
            flash(
                f'Stok telur grade {grade} tidak mencukupi. Maksimum hanya {len(eggs)} butir.',
                'error'
            )
            return redirect(url_for('eggmonitor_controller.eggmonitor_seller'))

        egg_ids = [row['id'] for row in eggs]

        # ==========================
        # 2) Tandai telur-telur baru sebagai listed dengan harga baru
        # ==========================
        placeholder = ','.join(['%s'] * len(egg_ids))
        params = [price] + egg_ids
        cur.execute(f"""
            UPDATE egg_scans
            SET status = 'listed',
                is_listed = TRUE,
                listed_price = %s,
                listed_at = NOW()
            WHERE id IN ({placeholder})
        """, params)

        # ==========================
        # 3) Kalau sudah ada listing dan harga berubah,
        #    update SEMUA telur listed grade ini ke harga baru
        #    (supaya konsisten: 1 grade = 1 harga)
        # ==========================
        if existing_listing is not None and existing_price != price:
            cur.execute("""
                UPDATE egg_scans
                SET listed_price = %s
                WHERE user_id = %s
                  AND grade = %s
                  AND status = 'listed'
                  AND is_listed = TRUE
            """, (price, seller_id, grade))

        # ==========================
        # 4) Hitung total stok listed untuk grade ini
        # ==========================
        cur.execute("""
            SELECT COUNT(*) AS total
            FROM egg_scans
            WHERE user_id = %s
              AND grade = %s
              AND status = 'listed'
        """, (seller_id, grade))
        total_stock = cur.fetchone()['total']

        # ==========================
        # 5) Insert / update egg_listings (1 row per seller+grade)
        #    price_per_egg = harga terbaru
        # ==========================
        cur.execute("""
            INSERT INTO egg_listings
                (seller_id, grade, stock_eggs, price_per_egg, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, 'active', NOW(), NOW())
            ON DUPLICATE KEY UPDATE
                stock_eggs    = VALUES(stock_eggs),
                price_per_egg = VALUES(price_per_egg),
                status        = 'active',
                updated_at    = NOW()
        """, (seller_id, grade, total_stock, price))

        conn.commit()
        # Tambahin info kecil biar seller paham perilaku sistem
        if existing_listing is not None and existing_price != price:
            flash(
                f'Listing grade {grade} diperbarui: stok sekarang {total_stock} butir, '
                f'harga diubah dari {int(existing_price)} menjadi {int(price)}.',
                'success'
            )
        else:
            flash(
                f'Listing grade {grade} berhasil disimpan. Stok sekarang {total_stock} butir.',
                'success'
            )

    except mysql.connector.Error as e:
        conn.rollback()
        print("Error save_listing:", e)
        flash('Terjadi kesalahan saat menyimpan listing.', 'error')
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('eggmonitor_controller.eggmonitor_seller'))

# ==============================================================================
# 1. KATALOG
# ==============================================================================

@eggmart_controller.route('/catalog')
@login_required
def eggmart():
    """EggMart catalog page (untuk PEMBELI) with Filtering"""
    now = datetime.now()
    sellers = []

    # Get Filter Params
    search_query = request.args.get('q', '').strip()
    price_max = request.args.get('price_max', type=int)
    grades = request.args.getlist('grade') 
    locations = request.args.getlist('location') 

    conn = get_db_connection()
    unique_locations = [] # List untuk menampung lokasi toko

    if conn:
        try:
            cur = conn.cursor(dictionary=True)

            # --- NEW: Ambil daftar lokasi unik dari Pengusaha ---
            cur.execute("""
                SELECT DISTINCT farm_location 
                FROM users 
                WHERE role = 'pengusaha' 
                  AND farm_location IS NOT NULL 
                  AND farm_location != ''
                ORDER BY farm_location
            """)
            loc_rows = cur.fetchall()
            unique_locations = [row['farm_location'] for row in loc_rows]

            # Base Query: Ambil Seller yang punya listing AKTIF
            sql = """
                SELECT 
                    u.id,
                    u.name,
                    u.farm_location,
                    COALESCE(AVG(r.rating), 0) AS rating,
                    COUNT(r.id) AS review_count
                FROM users u
                JOIN egg_listings el ON el.seller_id = u.id AND el.status = 'active'
                LEFT JOIN seller_ratings r ON r.seller_id = u.id
                WHERE u.role = 'pengusaha'
            """
            params = []

            # 3. Terapkan Filter Search (Nama Toko)
            if search_query:
                sql += " AND u.name LIKE %s"
                params.append(f"%{search_query}%")

            # 4. Terapkan Filter Lokasi (OR logic)
            if locations:
                loc_conditions = []
                for loc in locations:
                    if loc == 'nearby': continue # Skip logika geo kompleks dulu
                    loc_conditions.append("u.farm_location LIKE %s")
                    params.append(f"%{loc}%")
                
                if loc_conditions:
                    sql += f" AND ({' OR '.join(loc_conditions)})"

            # 5. Terapkan Filter Harga & Grade (Pada level Seller)
            # Kita filter seller yang MEMILIKI setidaknya satu produk yang sesuai kriteria
            if price_max:
                # Seller harus punya barang dengan harga <= max
                sql += " AND EXISTS (SELECT 1 FROM egg_listings el2 WHERE el2.seller_id = u.id AND el2.status='active' AND el2.price_per_egg <= %s)"
                params.append(price_max)
            
            if grades:
                # Seller harus punya barang dengan grade yang dipilih
                placeholders = ','.join(['%s'] * len(grades))
                sql += f" AND EXISTS (SELECT 1 FROM egg_listings el3 WHERE el3.seller_id = u.id AND el3.status='active' AND el3.grade IN ({placeholders}))"
                params.extend(grades)

            # Grouping & Ordering
            sql += " GROUP BY u.id, u.name, u.farm_location ORDER BY u.name"

            # Eksekusi Query Seller
            cur.execute(sql, tuple(params))
            seller_rows = cur.fetchall()

            for row in seller_rows:
                code = (row["name"] or "SL")[:2].upper()

                # 6. Ambil Produk per Seller (Filter Produknya Juga!)
                prod_sql = """
                    SELECT id, grade, stock_eggs, price_per_egg
                    FROM egg_listings
                    WHERE seller_id = %s AND status = 'active'
                """
                prod_params = [row["id"]]

                # Filter produk sesuai kriteria user agar yang tampil relevan
                if price_max:
                    prod_sql += " AND price_per_egg <= %s"
                    prod_params.append(price_max)
                
                if grades:
                    placeholders = ','.join(['%s'] * len(grades))
                    prod_sql += f" AND grade IN ({placeholders})"
                    prod_params.extend(grades)

                prod_sql += " ORDER BY grade"

                cur2 = conn.cursor(dictionary=True)
                cur2.execute(prod_sql, tuple(prod_params))
                product_rows = cur2.fetchall()
                cur2.close()

                # Jika setelah difilter seller tidak punya produk (misal harganya ketinggian semua), skip seller ini
                if not product_rows and (price_max or grades):
                    continue

                products = [
                    {
                        "id": p["id"],
                        "grade": p["grade"],
                        "stock": p["stock_eggs"],
                        "price": p["price_per_egg"],
                        "description": f"Telur grade {p['grade']} siap kirim",
                    }
                    for p in product_rows
                ]

                sellers.append({
                    "id": row["id"],
                    "code": code,
                    "name": row["name"],
                    "location": row["farm_location"] or "-",
                    "rating": float(row["rating"] or 0),
                    "review_count": int(row["review_count"] or 0),
                    "products": products,
                })

            cur.close()
        finally:
            conn.close()

    # Kembalikan data filters ke template agar input tidak kereset
    current_filters = {
        'q': search_query,
        'price_max': price_max,
        'grades': grades,
        'locations': locations
    }

    return render_template(
        "eggmart/catalog.html",
        sellers=sellers,
        active_menu="catalog",
        now=now,
        filters=current_filters
    )

@eggmart_controller.route('/api/catalog/filter', methods=['GET'])
@login_required
def api_filter_catalog():
    """
    API untuk mengambil daftar toko.
    Logika Baru: Tampilkan SEMUA user role='pengusaha', walaupun belum punya listing.
    """
    search_query = request.args.get('q', '').strip()
    price_max = request.args.get('price_max', type=int)
    grades = request.args.getlist('grade')
    locations = request.args.getlist('location')

    conn = get_db_connection()
    sellers = []
    
    if conn:
        try:
            cur = conn.cursor(dictionary=True)

            # 1. Ambil SEMUA Pengusaha (tanpa JOIN ke listing dulu agar tidak terfilter)
            sql = """
                SELECT 
                    u.id, u.name, u.farm_location, u.farm_name,
                    COALESCE(AVG(r.rating), 0) AS rating,
                    COUNT(r.id) AS review_count
                FROM users u
                LEFT JOIN seller_ratings r ON r.seller_id = u.id
                WHERE u.role = 'pengusaha'
            """
            params = []

            # Filter Search & Lokasi (Filter level User)
            if search_query:
                sql += " AND (u.name LIKE %s OR u.farm_name LIKE %s)"
                params.extend([f"%{search_query}%", f"%{search_query}%"])

            if locations:
                loc_conditions = []
                for loc in locations:
                    loc_conditions.append("u.farm_location LIKE %s")
                    params.append(f"%{loc}%")
                if loc_conditions:
                    sql += f" AND ({' OR '.join(loc_conditions)})"

            # (Opsional) Filter Harga/Grade bisa ditambahkan di sini dengan subquery EXISTS
            # Tapi agar toko tetap muncul (walau kosong), kita filter di level Python saja atau biarkan lolos.
            
            sql += " GROUP BY u.id, u.name, u.farm_location, u.farm_name ORDER BY u.name"

            cur.execute(sql, tuple(params))
            seller_rows = cur.fetchall()

            for row in seller_rows:
                code = (row["name"] or "SL")[:2].upper()
                
                # 2. Ambil Listing Aktif untuk Seller ini
                cur2 = conn.cursor(dictionary=True)
                cur2.execute("""
                    SELECT id, grade, stock_eggs, price_per_egg
                    FROM egg_listings
                    WHERE seller_id = %s AND status = 'active'
                """, (row['id'],))
                db_listings = {item['grade']: item for item in cur2.fetchall()}
                cur2.close()

                # 3. Normalisasi Produk (FORCE A, B, C)
                # Kita paksa agar Grade A, B, C selalu ada di list produk
                products = []
                
                # Jika user memfilter grade, gunakan itu. Jika tidak, tampilkan semua.
                target_grades = grades if grades else ['A', 'B', 'C']

                has_matching_product = False # Flag untuk filter harga/grade

                for grade in target_grades:
                    data = db_listings.get(grade)
                    
                    if data:
                        # === KASUS 1: Penjual PUNYA stok ini ===
                        # Cek filter harga (jika ada)
                        if price_max and data['price_per_egg'] > price_max:
                             continue # Skip jika harganya kemahalan (sesuai filter user)

                        products.append({
                            "id": data["id"],
                            "grade": grade,
                            "stock": data["stock_eggs"],
                            "price": data["price_per_egg"],
                            "description": f"Telur grade {grade} siap kirim"
                        })
                        has_matching_product = True
                    else:
                        # === KASUS 2: Penjual TIDAK PUNYA stok ini (Listing belum dibuat) ===
                        # Kita buat Dummy Product agar tampilan tidak kosong
                        # ID 0 menandakan "Fake/Dummy"
                        products.append({
                            "id": 0, 
                            "grade": grade,
                            "stock": 0, 
                            "price": 0, 
                            "description": "Stok belum tersedia"
                        })
                        # Produk kosong dianggap tidak match filter harga (karena harga 0/ga ada)
                
                # Logic Akhir: 
                # Jika user sedang melakukan filter spesifik (misal: cari harga < 2000),
                # dan toko ini tidak punya satupun barang yg sesuai, haruskah toko ini muncul?
                # Jika ingin tetap muncul (kosong), hapus 'if' di bawah.
                # Jika ingin disembunyikan saat tidak relevan, biarkan 'if' ini.
                if (price_max or grades) and not has_matching_product:
                     continue 

                sellers.append({
                    "id": row["id"],
                    "code": code,
                    "name": row["farm_name"] or row["name"], # Prioritaskan nama Farm
                    "location": row["farm_location"] or "-",
                    "rating": float(row["rating"] or 0),
                    "review_count": int(row["review_count"] or 0),
                    "products": products,
                    "detail_url": url_for('eggmart_controller.eggmartDetail', seller_id=row["id"])
                })

            cur.close()
        finally:
            conn.close()
            
    return jsonify({'success': True, 'sellers': sellers})
    
# ==============================================================================
# 2. KATALOG = API UPDATE PROFILE 
# ==============================================================================

@eggmart_controller.route('/api/profile/update', methods=['POST'])
@login_required
def update_profile():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    location = data.get('location') # Field baru dari frontend
    
    # Validasi dasar
    if not name or not email:
        return jsonify({'success': False, 'message': 'Nama dan Email wajib diisi'}), 400
        
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            
            # 1. Cek validitas email (apakah dipakai user lain?)
            cur.execute("SELECT id FROM users WHERE email = %s AND id != %s", (email, current_user.id))
            if cur.fetchone():
                return jsonify({'success': False, 'message': 'Email sudah digunakan'}), 400
            
            # 2. Update User (termasuk lokasi ke farm_location)
            # Kita update farm_location meskipun user adalah pembeli (karena struktur DB menggunakan kolom itu untuk lokasi)
            cur.execute("""
                UPDATE users 
                SET name = %s, 
                    email = %s, 
                    farm_location = %s 
                WHERE id = %s
            """, (name, email, location, current_user.id))
            
            conn.commit()
            cur.close()
            return jsonify({'success': True, 'message': 'Profil & Lokasi berhasil diperbarui'})
            
        except Exception as e:
            print("Update profile error:", e)
            return jsonify({'success': False, 'message': 'Terjadi kesalahan server'}), 500
        finally:
            conn.close()
            
    return jsonify({'success': False, 'message': 'Database error'}), 500

@eggmart_controller.route('/detail/<int:seller_id>')
@login_required
def eggmartDetail(seller_id):
    """
    Halaman Detail Toko.
    Menampilkan Grade A, B, C meskipun penjual belum pernah input data.
    """
    now = datetime.now()
    conn = get_db_connection()
    seller = None
    reviews = []

    if conn:
        try:
            cur = conn.cursor(dictionary=True)

            # Info Penjual
            cur.execute("""
                SELECT 
                    u.id, u.name, u.farm_name, u.farm_location,
                    COALESCE(AVG(r.rating), 0) AS rating,
                    COUNT(r.id) AS review_count
                FROM users u
                LEFT JOIN seller_ratings r ON r.seller_id = u.id
                WHERE u.id = %s AND u.role = 'pengusaha'
                GROUP BY u.id, u.name, u.farm_name, u.farm_location
            """, (seller_id,))
            row = cur.fetchone()
            
            if not row:
                flash("Penjual tidak ditemukan.", "error")
                return redirect(url_for("eggmart_controller.eggmart"))

            seller = {
                "id": row["id"],
                "code": (row["name"][:2] if row["name"] else "SL").upper(),
                "name": row["farm_name"] or row["name"],
                "location": row["farm_location"] or "-",
                "rating": float(row["rating"] or 0),
                "review_count": int(row["review_count"] or 0),
            }

            # Listing Aktif
            cur.execute("""
                SELECT id, grade, stock_eggs, price_per_egg
                FROM egg_listings
                WHERE seller_id = %s AND status = 'active'
            """, (seller_id,))
            db_listings = {item['grade']: item for item in cur.fetchall()}

            # Generate Produk Lengkap (A, B, C)
            final_products = []
            for grade in ['A', 'B', 'C']:
                data = db_listings.get(grade)
                if data:
                    final_products.append({
                        "id": data["id"],
                        "grade": grade,
                        "stock": data["stock_eggs"],
                        "price": data["price_per_egg"],
                        "description": f"Telur grade {grade} siap kirim"
                    })
                else:
                    # Produk Dummy (Stok Habis)
                    final_products.append({
                        "id": 0, 
                        "grade": grade,
                        "stock": 0,
                        "price": 0,
                        "description": "Stok belum tersedia"
                    })

            seller["products"] = final_products

            # Reviews
            cur.execute("""
                SELECT buyer_id, buyer_name, rating, review, created_at
                FROM seller_ratings
                WHERE seller_id = %s
                ORDER BY created_at ASC
            """, (seller_id,))
            reviews = cur.fetchall()

            cur.close()
        finally:
            conn.close()

    return render_template(
        "eggmart/catalog_detail.html",
        seller=seller,
        reviews=reviews,
        active_menu="catalog",
        now=now,
        midtrans_client_key=current_app.config.get("MIDTRANS_CLIENT_KEY")
    )

# ==========================
# 2. KATALOG = API CHAT BUYER <-> SELLER
# ==========================

@eggmart_controller.route('/chat/<int:seller_id>', methods=['GET'])
@login_required
def get_chat_for_seller(seller_id):
    """
    Ambil (atau buat) sesi chat antara buyer (current_user) dengan seller_id tertentu.
    Mengembalikan riwayat pesan untuk ditampilkan di modal chat.
    """
    buyer_id = current_user.id
    conn = get_db_connection()
    if not conn:
        return jsonify(success=False, message="Gagal koneksi database"), 500

    try:
        cur = conn.cursor(dictionary=True)

        # Pastikan seller valid
        cur.execute("SELECT id, name FROM users WHERE id = %s AND role = 'pengusaha'", (seller_id,))
        seller = cur.fetchone()
        if not seller:
            return jsonify(success=False, message="Penjual tidak ditemukan"), 404

        # Cari session. Kita cek berdasarkan user_id AND seller_id
        cur.execute("""
            SELECT id
            FROM chat_sessions
            WHERE user_id = %s AND seller_id = %s
            LIMIT 1
        """, (buyer_id, seller_id))
        row = cur.fetchone()

        if row:
            session_id = row['id']
        else:
            # === FIX: Create session dengan mengisi kolom SELLER_ID ===
            cur.execute("""
                INSERT INTO chat_sessions (user_id, seller_id, guest_email, guest_name, status, last_message_at, created_at)
                VALUES (%s, %s, %s, %s, 'active', NOW(), NOW())
            """, (buyer_id, seller_id, f"seller:{seller_id}", seller['name']))
            session_id = cur.lastrowid
            conn.commit()

        # Ambil semua pesan chat utk session ini
        cur.execute("""
            SELECT id, message, message_type, created_at
            FROM chat_messages
            WHERE session_id = %s
            ORDER BY created_at ASC
        """, (session_id,))

        msgs = []
        for m in cur.fetchall():
            mtype = m['message_type']
            # === FIX: Logic penentuan sender 'self' ===
            # Jika tipe pesan adalah pembeli_to_pengusaha, itu adalah 'self' (karena yg login pembeli)
            if mtype == 'pembeli_to_pengusaha' or mtype == 'user_to_admin':
                sender = 'self'
            else:
                sender = 'seller'

            msgs.append({
                "id": m["id"],
                "sender": sender,
                "text": m["message"],
                "time": m["created_at"].strftime("%H:%M") if m["created_at"] else ""
            })

        cur.close()
        return jsonify(
            success=True,
            session_id=session_id,
            seller_name=seller["name"],
            messages=msgs
        )

    except mysql.connector.Error as e:
        print("get_chat_for_seller error:", e)
        return jsonify(success=False, message="Error database"), 500
    finally:
        conn.close()

@eggmart_controller.route('/chat/<int:seller_id>', methods=['POST'])
@login_required
def send_chat_to_seller(seller_id):
    """
    Kirim pesan baru dari buyer -> seller dalam sesi chat.
    """
    buyer_id = current_user.id
    data = request.get_json(silent=True) or {}
    text = (data.get("message") or "").strip()

    if not text:
        return jsonify(success=False, message="Pesan tidak boleh kosong"), 400

    conn = get_db_connection()
    if not conn:
        return jsonify(success=False, message="Gagal koneksi database"), 500

    try:
        cur = conn.cursor(dictionary=True)

        # Pastikan seller valid
        cur.execute("SELECT id, name FROM users WHERE id = %s AND role = 'pengusaha'", (seller_id,))
        seller = cur.fetchone()
        if not seller:
            return jsonify(success=False, message="Penjual tidak ditemukan"), 404

        # Cari session berdasarkan seller_id (Recommended) atau guest_email (Legacy fallback)
        cur.execute("""
            SELECT id
            FROM chat_sessions
            WHERE user_id = %s AND (seller_id = %s OR guest_email = %s)
            LIMIT 1
        """, (buyer_id, seller_id, f"seller:{seller_id}"))
        row = cur.fetchone()

        if row:
            session_id = row['id']
            # Optional: Pastikan seller_id terisi jika sebelumnya NULL (untuk data lama)
            cur.execute("UPDATE chat_sessions SET seller_id = %s WHERE id = %s AND seller_id IS NULL", (seller_id, session_id))
        else:
            # === FIX: Insert SELLER_ID agar muncul di dashboard Pengusaha ===
            cur.execute("""
                INSERT INTO chat_sessions (user_id, seller_id, guest_email, guest_name, status, last_message_at, created_at)
                VALUES (%s, %s, %s, %s, 'active', NOW(), NOW())
            """, (buyer_id, seller_id, f"seller:{seller_id}", seller['name']))
            session_id = cur.lastrowid

        # === FIX: Gunakan message_type 'pembeli_to_pengusaha' ===
        # Ini penting agar API dashboard seller bisa menghitung unread_count dengan benar
        cur.execute("""
            INSERT INTO chat_messages (
                session_id, user_id, message, message_type, status, created_at
            )
            VALUES (%s, %s, %s, 'pembeli_to_pengusaha', 'unread', NOW())
        """, (session_id, buyer_id, text))

        # Update last_message_at session
        cur.execute("""
            UPDATE chat_sessions
            SET last_message = %s, last_message_at = NOW()
            WHERE id = %s
        """, (text, session_id))

        conn.commit()
        cur.close()

        now_time = datetime.now().strftime("%H:%M")

        return jsonify(
            success=True,
            session_id=session_id,
            message={"sender": "self", "text": text, "time": now_time}
        )

    except mysql.connector.Error as e:
        conn.rollback()
        print("send_chat_to_seller error:", e)
        return jsonify(success=False, message="Error database"), 500
    finally:
        conn.close()

@eggmart_controller.route('/chat/start/<int:seller_id>')
@login_required
def start_chat(seller_id):
    """
    Buyer starts or resumes a chat with a specific seller from the catalog.
    """
    if current_user.role != 'pembeli':
        flash("Hanya pembeli yang bisa memulai chat.", "error")
        return redirect(url_for('eggmart_controller.eggmart'))

    conn = get_db_connection()
    session_id = None
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # 1. Check if a session already exists
        # We use a unique constraint logic: user_id + seller_id
        cur.execute("""
            SELECT id FROM chat_sessions 
            WHERE user_id = %s AND seller_id = %s
        """, (current_user.id, seller_id))
        row = cur.fetchone()
        
        if row:
            session_id = row['id']
        else:
            # 2. Get Seller Info for the guest_name/email fallback (optional)
            cur.execute("SELECT name, email FROM users WHERE id=%s", (seller_id,))
            seller = cur.fetchone()
            
            # 3. Create new session
            # Note: guest_email/name is technically redundant for registered users 
            # but good for fallback. We set status='active'.
            cur.execute("""
                INSERT INTO chat_sessions (user_id, seller_id, status, created_at, last_message_at)
                VALUES (%s, %s, 'active', NOW(), NOW())
            """, (current_user.id, seller_id))
            conn.commit()
            session_id = cur.lastrowid
            
        cur.close()
    finally:
        conn.close()

    # Redirect to the chat room UI
    return redirect(url_for('eggmart_controller.chat_room', session_id=session_id))

@eggmart_controller.route('/chat/room/<int:session_id>')
@login_required
def chat_room(session_id):
    """
    The UI for the Buyer to chat.
    """
    if current_user.role != 'pembeli':
        return redirect(url_for('eggmart_controller.eggmart'))

    conn = get_db_connection()
    messages = []
    seller_info = {}
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # 1. Verify Session Ownership & Get Seller Details
        cur.execute("""
            SELECT cs.*, u.name as seller_name, u.farm_name 
            FROM chat_sessions cs
            JOIN users u ON cs.seller_id = u.id
            WHERE cs.id = %s AND cs.user_id = %s
        """, (session_id, current_user.id))
        session_data = cur.fetchone()
        
        if not session_data:
            flash("Chat tidak ditemukan.", "error")
            return redirect(url_for('eggmart_controller.eggmart'))
            
        seller_info = {
            'name': session_data['farm_name'] or session_data['seller_name'],
            'id': session_data['seller_id']
        }

        # 2. Get Messages
        cur.execute("""
            SELECT * FROM chat_messages 
            WHERE session_id = %s 
            ORDER BY created_at ASC
        """, (session_id,))
        rows = cur.fetchall()
        
        for r in rows:
            # Determine sender for UI class (me vs them)
            sender = 'me' if r['message_type'] == 'pembeli_to_pengusaha' else 'them'
            messages.append({
                'text': r['message'],
                'sender': sender,
                'time': r['created_at'].strftime('%H:%M')
            })
        
        cur.close()
    finally:
        conn.close()

    return render_template('eggmart/chat_room.html', session_id=session_id, messages=messages, seller=seller_info)

@eggmart_controller.route('/api/chat/send', methods=['POST'])
@login_required
def api_buyer_send_chat():
    """API for Buyer sending message"""
    session_id = request.form.get('session_id')
    message = request.form.get('message')
    
    if not message or not session_id:
        return jsonify({'success': False, 'error': 'Empty data'}), 400

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # Insert message (Type: pembeli_to_pengusaha)
        cur.execute("""
            INSERT INTO chat_messages (session_id, user_id, message, message_type, status, created_at)
            VALUES (%s, %s, %s, 'pembeli_to_pengusaha', 'unread', NOW())
        """, (session_id, current_user.id, message))
        
        # Update session timestamp
        cur.execute("""
            UPDATE chat_sessions SET last_message = %s, last_message_at = NOW()
            WHERE id = %s
        """, (message, session_id))
        
        conn.commit()
        cur.close()
        return jsonify({'success': True})
    finally:
        conn.close()

# ==============================================================================
# 3. HISTORY
# ==============================================================================

@eggmart_controller.route('/history')
@login_required
def eggmartHistory():
    """
    Halaman riwayat transaksi dengan fitur Auto-Sync ke Midtrans.
    Memastikan status 'paid/settlement' muncul meskipun webhook tidak jalan di localhost.
    """
    now = datetime.now()
    buyer_orders = []

    conn = get_db_connection()
    if not conn:
        flash("Gagal koneksi ke database.", "error")
        return redirect(url_for('eggmart_controller.eggmart'))

    try:
        cur = conn.cursor(dictionary=True)

        # ==================================================================
        # 1. SYNC STATUS DENGAN MIDTRANS (WAJIB UNTUK LOCALHOST)
        # ==================================================================
        # Ambil semua order user ini yang masih 'pending'
        cur.execute("""
            SELECT id, midtrans_order_id 
            FROM orders 
            WHERE buyer_id = %s AND status = 'pending'
        """, (current_user.id,))
        pending_list = cur.fetchall()

        if pending_list:
            server_key = current_app.config.get("MIDTRANS_SERVER_KEY")
            is_prod = current_app.config.get("MIDTRANS_IS_PRODUCTION", False)
            base_url = "https://api.midtrans.com" if is_prod else "https://api.sandbox.midtrans.com"
            
            # Header Auth untuk API Midtrans
            auth_string = base64.b64encode((server_key + ':').encode()).decode('utf-8')
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Basic {auth_string}"
            }

            for p_order in pending_list:
                try:
                    # Cek status ke Midtrans
                    url = f"{base_url}/v2/{p_order['midtrans_order_id']}/status"
                    resp = requests.get(url, headers=headers, timeout=5)
                    
                    if resp.status_code == 200:
                        res_data = resp.json()
                        m_status = res_data.get('transaction_status')
                        
                        # Mapping status Midtrans ke Database Enum
                        new_status = None
                        if m_status == 'settlement':
                            new_status = 'settlement'
                        elif m_status == 'capture':
                            new_status = 'capture'
                        elif m_status in ['deny', 'cancel', 'expire']:
                            new_status = 'expired' # Sesuai enum DB Anda
                        
                        # Jika status berubah menjadi sukses, update DB
                        if new_status and new_status in ['settlement', 'capture']:
                            # 1. Update Status Order
                            cur.execute("UPDATE orders SET status = %s, updated_at = NOW() WHERE id = %s", (new_status, p_order['id']))
                            
                            # 2. Update Stok Telur jadi 'sold' (PENTING agar tidak menggantung)
                            cur.execute("""
                                UPDATE egg_scans es
                                JOIN order_items oi ON oi.egg_scan_id = es.id
                                SET es.status = 'sold'
                                WHERE oi.order_id = %s AND es.status != 'sold'
                            """, (p_order['id'],))
                            
                        elif new_status == 'expired':
                             # Jika expired di midtrans, update di DB
                             cur.execute("UPDATE orders SET status = 'expired', updated_at = NOW() WHERE id = %s", (p_order['id'],))

                except Exception as e:
                    print(f"Gagal sync order {p_order['midtrans_order_id']}: {e}")
            
            # Commit perubahan sync
            conn.commit()

        # ==================================================================
        # 2. LOGIKA AUTO-EXPIRE LAMA (BACKUP)
        # ==================================================================
        # Tetap disimpan untuk membersihkan order yang tidak ada di Midtrans
        expiry_time = now - timedelta(hours=1) 
        cur.execute("""
            UPDATE orders 
            SET status = 'expired' 
            WHERE status = 'pending' AND created_at < %s
        """, (expiry_time,))
        conn.commit()

        # ==================================================================
        # 3. FETCH DATA UNTUK TAMPILAN
        # ==================================================================
        cur.execute("""
            SELECT 
                o.id,
                o.midtrans_order_id,
                o.midtrans_transaction_id AS snap_token, 
                o.total,
                o.status,
                o.created_at,
                s.name AS seller_name,
                u.farm_name,
                u.farm_location,
                COALESCE(SUM(oi.quantity), 0) AS total_eggs
            FROM orders o
            LEFT JOIN users s ON s.id = o.seller_id
            LEFT JOIN users u ON u.id = o.seller_id
            LEFT JOIN order_items oi ON oi.order_id = o.id
            WHERE o.buyer_id = %s
            GROUP BY 
                o.id, o.midtrans_order_id, o.midtrans_transaction_id, o.total, o.status, 
                o.created_at, seller_name, u.farm_name, u.farm_location
            ORDER BY o.created_at DESC
        """, (current_user.id,))
        
        rows = cur.fetchall()

        # Fetch Detail Item
        if rows:
            order_ids = [str(r['id']) for r in rows]
            placeholders = ','.join(order_ids)
            
            cur.execute(f"""
                SELECT oi.order_id, oi.quantity, oi.price, es.grade
                FROM order_items oi
                JOIN egg_scans es ON es.id = oi.egg_scan_id
                WHERE oi.order_id IN ({placeholders})
            """)
            items = cur.fetchall()
            
            items_map = {}
            for item in items:
                oid = item['order_id']
                if oid not in items_map: items_map[oid] = []
                items_map[oid].append(item)

            for r in rows:
                r_items = items_map.get(r['id'], [])
                
                # Generate Description text
                grade_counts = {}
                for i in r_items:
                    g = i['grade']
                    grade_counts[g] = grade_counts.get(g, 0) + i['quantity']
                desc_parts = [f"Grade {g} ({q}x)" for g, q in grade_counts.items()]
                
                buyer_orders.append({
                    "id": r['id'],
                    "code": r['midtrans_order_id'],
                    "snap_token": r['snap_token'], 
                    "seller_name": r['farm_name'] or r['seller_name'],
                    "location": r['farm_location'],
                    "total": float(r['total'] or 0),
                    "status": r['status'], 
                    "date": r['created_at'],
                    "total_qty": int(r['total_eggs'] or 0),
                    "description": ", ".join(desc_parts),
                    "items": r_items
                })

        cur.close()
    except mysql.connector.Error as e:
        print("eggmartHistory DB error:", e)
    finally:
        conn.close()

    # Cek new_order_code dari redirect pembayaran
    new_order_code = request.args.get('new_order_code')
    new_order_data = next((o for o in buyer_orders if o['code'] == new_order_code), None)

    return render_template(
        'eggmart/history.html',
        orders=buyer_orders,
        new_order=new_order_data,
        active_menu='history',
        midtrans_client_key=current_app.config.get("MIDTRANS_CLIENT_KEY") 
    )

@eggmart_controller.route('/transaction', methods=['POST'])
@login_required
def create_transaction():
    """
    Buat transaksi baru.
    Logic update: Validasi fleksibel (bisa via listing_id ATAU grade+seller_id).
    """
    is_json = request.headers.get('Content-Type', '').startswith('application/json') or request.is_json
    data = request.get_json(silent=True) if is_json else request.form

    try:
        # Ambil semua parameter yang mungkin dikirim
        listing_id = int(data.get('listing_id', 0)) 
        quantity = int(data.get('quantity', 0))
        grade_input = data.get('grade') 
        seller_id_input = int(data.get('seller_id', 0))
    except (TypeError, ValueError):
        listing_id = 0
        quantity = 0
        grade_input = None
        seller_id_input = 0

    # 1. Validasi Quantity
    if quantity <= 0:
        msg = "Jumlah pesanan minimal 1."
        if is_json: return jsonify(success=False, message=msg), 400
        flash(msg, "error")
        return redirect(url_for('eggmart_controller.eggmart'))

    # 2. Validasi Target: Harus ada Listing ID ATAU (Seller ID + Grade)
    # Ini yang memperbaiki error "Listing tidak valid" sebelumnya
    if listing_id <= 0 and (not grade_input or seller_id_input <= 0):
        msg = "Data produk tidak valid (ID Listing atau Grade/Penjual hilang)."
        if is_json: return jsonify(success=False, message=msg), 400
        flash(msg, "error")
        return redirect(url_for('eggmart_controller.eggmart'))

    conn = get_db_connection()
    if not conn:
        if is_json: return jsonify(success=False, message="Gagal koneksi database."), 500
        flash("Gagal koneksi database.", "error")
        return redirect(url_for('eggmart_controller.eggmart'))

    try:
        cur = conn.cursor(dictionary=True)
        
        listing = None
        
        # A. Coba cari by Listing ID (jika ada)
        if listing_id > 0:
            cur.execute("SELECT * FROM egg_listings WHERE id = %s AND status='active'", (listing_id,))
            listing = cur.fetchone()
        
        # B. Fallback: Cari listing by Seller + Grade (jika ID 0 atau tidak ketemu)
        if not listing and grade_input and seller_id_input:
            cur.execute("SELECT * FROM egg_listings WHERE seller_id = %s AND grade = %s AND status='active'", (seller_id_input, grade_input))
            listing = cur.fetchone()

        # Jika masih tidak ketemu, berarti penjual belum set harga di menu Listing
        if not listing:
            msg = "Produk ini belum diberi harga oleh penjual (Listing belum dibuat)."
            if is_json: return jsonify(success=False, message=msg), 400
            flash(msg, "error")
            return redirect(url_for('eggmart_controller.eggmartDetail', seller_id=seller_id_input))

        # Ambil data final dari listing yang ditemukan
        seller_id = listing['seller_id']
        grade = listing['grade']
        price = float(listing['price_per_egg'])
        
        # 3. Cek Stok REAL dari egg_scans
        # Kita ambil ID telur spesifik yang akan dijual
        cur.execute("""
            SELECT id FROM egg_scans 
            WHERE user_id = %s 
              AND grade = %s 
              AND status = 'available' 
              AND (is_listed = FALSE OR is_listed IS NULL)
            LIMIT %s
        """, (seller_id, grade, quantity))
        egg_rows = cur.fetchall()

        if len(egg_rows) < quantity:
            msg = f"Stok tidak mencukupi. Hanya tersisa {len(egg_rows)} butir."
            if is_json: return jsonify(success=False, message=msg), 400
            flash(msg, "error")
            return redirect(url_for('eggmart_controller.eggmartDetail', seller_id=seller_id))

        egg_ids = [r['id'] for r in egg_rows]
        total = price * quantity
        order_id_str = f"EGG-{int(time.time())}-{current_user.id}"

        # 4. Insert Order Header
        cur.execute("""
            INSERT INTO orders (buyer_id, seller_id, total, midtrans_order_id, status, payment_type, created_at)
            VALUES (%s, %s, %s, %s, 'pending', 'midtrans_snap', NOW())
        """, (current_user.id, seller_id, total, order_id_str))
        order_db_id = cur.lastrowid

        # 5. Insert Order Items & Update Status Telur
        for eid in egg_ids:
            cur.execute("INSERT INTO order_items (order_id, egg_scan_id, price, quantity) VALUES (%s, %s, %s, 1)", (order_db_id, eid, price))
        
        placeholders = ','.join(['%s'] * len(egg_ids))
        cur.execute(f"UPDATE egg_scans SET status = 'sold' WHERE id IN ({placeholders})", egg_ids)

        # 6. Update Listing Cache (Stok tampilan)
        new_stock = max(0, listing['stock_eggs'] - quantity)
        cur.execute("UPDATE egg_listings SET stock_eggs = %s WHERE id = %s", (new_stock, listing['id']))

        conn.commit()

        # 7. Midtrans Snap Request
        snap_token = None
        server_key = current_app.config.get("MIDTRANS_SERVER_KEY")
        if server_key:
            try:
                snap = get_midtrans_snap()
                param = {
                    "transaction_details": {"order_id": order_id_str, "gross_amount": int(total)},
                    "credit_card": {"secure": True},
                    "customer_details": {"first_name": current_user.name, "email": current_user.email},
                    "item_details": [{"id": str(listing['id']), "price": int(price), "quantity": quantity, "name": f"Telur Grade {grade}"}]
                }
                transaction = snap.create_transaction(param)
                snap_token = transaction['token']
                
                # Simpan token ke DB
                cur.execute("UPDATE orders SET midtrans_transaction_id = %s WHERE id = %s", (snap_token, order_db_id))
                conn.commit()
            except Exception as e:
                print(f"Midtrans Error: {e}")

        cur.close()
        
        # Return JSON untuk Frontend JS
        if is_json:
            return jsonify(success=True, snap_token=snap_token, order_id=order_id_str)
        else:
            flash("Order berhasil dibuat.", "success")
            return redirect(url_for('eggmart_controller.eggmartHistory'))

    except Exception as e:
        if conn: conn.rollback()
        print(f"Transaction Error: {e}")
        if is_json: return jsonify(success=False, message="Terjadi kesalahan server"), 500
        flash("Terjadi kesalahan server.", "error")
        return redirect(url_for('eggmart_controller.eggmart'))
    finally:
        if conn: conn.close()

@eggmart_controller.route('/api/midtrans/notification', methods=['POST'])
def midtrans_notification():
    """
    Webhook untuk menerima notification dari Midtrans
    """
    try:
        data = request.get_json()
        if not data:
            print("Midtrans Notification: No JSON data received")
            return jsonify({'status': 'error', 'message': 'No data received'}), 400

        order_id = data.get('order_id')
        transaction_status = data.get('transaction_status')
        fraud_status = data.get('fraud_status')

        print(f"Midtrans Notification: {order_id} - {transaction_status} - Fraud: {fraud_status}")

        conn = get_db_connection()
        if not conn:
            print("Midtrans Notification: Database connection failed")
            return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500

        try:
            cur = conn.cursor(dictionary=True)
            
            # Cari order berdasarkan midtrans_order_id
            cur.execute("SELECT id, status FROM orders WHERE midtrans_order_id = %s", (order_id,))
            order = cur.fetchone()
            
            if not order:
                print(f"Midtrans Notification: Order not found: {order_id}")
                return jsonify({'status': 'error', 'message': 'Order not found'}), 404

            new_status = None
            
            # Update status berdasarkan notifikasi Midtrans
            if transaction_status == 'capture':
                if fraud_status == 'challenge':
                    new_status = 'challenge'
                else:
                    new_status = 'paid'
            elif transaction_status == 'settlement':
                new_status = 'settlement'
            elif transaction_status == 'pending':
                new_status = 'pending'
            elif transaction_status == 'deny':
                new_status = 'denied'
            elif transaction_status == 'expire':
                new_status = 'expired'
            elif transaction_status == 'cancel':
                new_status = 'cancelled'

            print(f"Current status: {order['status']}, New status: {new_status}")

            if new_status and new_status != order['status']:
                cur.execute("UPDATE orders SET status = %s, updated_at = NOW() WHERE id = %s", (new_status, order['id']))
                conn.commit()
                print(f"Order {order_id} status updated to: {new_status}")

                # If payment is successful, also update egg_scans status if needed
                if new_status in ['paid', 'settlement']:
                    cur.execute("""
                        UPDATE egg_scans es
                        JOIN order_items oi ON oi.egg_scan_id = es.id
                        JOIN orders o ON o.id = oi.order_id
                        SET es.status = 'sold'
                        WHERE o.id = %s AND es.status != 'sold'
                    """, (order['id'],))
                    conn.commit()
                    print(f"Updated egg_scans to 'sold' for order {order['id']}")

            cur.close()
            return jsonify({'status': 'ok', 'message': 'Notification processed'})

        except Exception as e:
            conn.rollback()
            print(f"Error processing Midtrans notification: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500
        finally:
            if conn:
                conn.close()

    except Exception as e:
        print(f"Midtrans notification error: {e}")
        return jsonify({'status': 'error', 'message': 'Processing failed'}), 500