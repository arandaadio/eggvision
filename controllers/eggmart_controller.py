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


@eggmart_controller.route('/transaction', methods=['POST'])
@login_required
def create_transaction():
    """
    Buat transaksi baru dari listing EggMart.
    - Validasi stok
    - Ambil telur 'listed' dari egg_scans
    - Simpan ke orders & order_items
    - Update egg_scans -> sold, update egg_listings.stock_eggs
    - (Opsional) panggil Midtrans Snap, balikin snap_token
    """
    # Bisa JSON (AJAX fetch) atau form POST biasa
    is_json = request.headers.get('Content-Type', '').startswith('application/json') or request.is_json
    data = request.get_json(silent=True) if is_json else request.form

    try:
        listing_id = int(data.get('listing_id', 0))
        quantity = int(data.get('quantity', 0))
    except (TypeError, ValueError):
        listing_id = 0
        quantity = 0

    if listing_id <= 0 or quantity <= 0:
        if is_json:
            return jsonify(success=False, message="Listing atau jumlah tidak valid."), 400
        flash("Listing atau jumlah tidak valid.", "error")
        return redirect(url_for('eggmart_controller.eggmart'))

    conn = get_db_connection()
    if not conn:
        if is_json:
            return jsonify(success=False, message="Gagal koneksi database."), 500
        flash("Gagal koneksi database.", "error")
        return redirect(url_for('eggmart_controller.eggmart'))

    seller_id = None
    try:
        cur = conn.cursor(dictionary=True)

        # 1) Ambil listing aktif
        cur.execute("""
            SELECT el.id, el.seller_id, el.grade, el.stock_eggs, el.price_per_egg,
                   u.name AS seller_name
            FROM egg_listings el
            JOIN users u ON u.id = el.seller_id
            WHERE el.id = %s AND el.status = 'active'
        """, (listing_id,))
        listing = cur.fetchone()

        if not listing:
            if is_json:
                return jsonify(success=False, message="Listing tidak ditemukan atau tidak aktif."), 404
            flash("Listing tidak ditemukan atau tidak aktif.", "error")
            return redirect(url_for('eggmart_controller.eggmart'))

        seller_id = listing['seller_id']
        price = float(listing['price_per_egg'])
        stock = int(listing['stock_eggs'])

        if quantity > stock:
            msg = f"Stok tidak mencukupi. Maksimum {stock} butir."
            if is_json:
                return jsonify(success=False, message=msg), 400
            flash(msg, "error")
            return redirect(url_for('eggmart_controller.eggmartDetail', seller_id=seller_id))

        # 2) Ambil telur yang sudah status 'listed'
        cur.execute("""
            SELECT id
            FROM egg_scans
            WHERE user_id = %s
              AND grade = %s
              AND status = 'listed'
              AND listed_price = %s
            ORDER BY listed_at ASC
            LIMIT %s
        """, (seller_id, listing['grade'], listing['price_per_egg'], quantity))
        egg_rows = cur.fetchall()

        if len(egg_rows) < quantity:
            msg = "Stok telur ter-list tidak mencukupi."
            if is_json:
                return jsonify(success=False, message=msg), 400
            flash(msg, "error")
            return redirect(url_for('eggmart_controller.eggmartDetail', seller_id=seller_id))

        egg_ids = [r['id'] for r in egg_rows]
        total = price * quantity

        # 3) Buat order_id unik untuk Midtrans
        order_id_str = f"EGG-{int(time.time())}-{listing_id}"

        # 4) Insert ke orders
        cur.execute("""
            INSERT INTO orders (
                buyer_id, seller_id, total,
                midtrans_order_id, status, payment_type, shipping_address,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """, (
            current_user.id,
            seller_id,
            total,
            order_id_str,
            'pending',
            'midtrans_snap',
            ''  # shipping_address bisa ditambah nanti
        ))
        order_db_id = cur.lastrowid

        # 5) Insert ke order_items (1 butir per row)
        for egg_id in egg_ids:
            cur.execute("""
                INSERT INTO order_items (order_id, egg_scan_id, price, quantity)
                VALUES (%s, %s, %s, 1)
            """, (order_db_id, egg_id, price))

        # 6) Update egg_scans -> sold
        placeholders = ','.join(['%s'] * len(egg_ids))
        cur.execute(f"""
            UPDATE egg_scans
            SET status = 'sold'
            WHERE id IN ({placeholders})
        """, egg_ids)

        # 7) Hitung ulang stok listed untuk listing ini
        cur.execute("""
            SELECT COUNT(*) AS listed_count
            FROM egg_scans
            WHERE user_id = %s
              AND grade = %s
              AND status = 'listed'
              AND listed_price = %s
        """, (seller_id, listing['grade'], listing['price_per_egg']))
        remaining = int(cur.fetchone()['listed_count'] or 0)

        cur.execute("""
            UPDATE egg_listings
            SET stock_eggs = %s,
                status = CASE WHEN %s = 0 THEN 'inactive' ELSE status END,
                updated_at = NOW()
            WHERE id = %s
        """, (remaining, remaining, listing_id))

        conn.commit()

        # 8) Panggil Midtrans Snap API (kalau SERVER_KEY di-set)
        snap_token = None
        midtrans_server_key = current_app.config.get("MIDTRANS_SERVER_KEY")
        midtrans_is_production = current_app.config.get("MIDTRANS_IS_PRODUCTION", False)

        if midtrans_server_key:
            base_url = "https://app.midtrans.com" if midtrans_is_production else "https://app.sandbox.midtrans.com"
            url = base_url + "/snap/v1/transactions"

            auth_str = base64.b64encode((midtrans_server_key + ":").encode()).decode()

            payload = {
                "transaction_details": {
                    "order_id": order_id_str,
                    "gross_amount": int(total),  # Midtrans minta integer
                },
                "credit_card": {
                    "secure": True
                },
                "customer_details": {
                    "first_name": current_user.name,
                    "email": getattr(current_user, "email", None),
                },
                "item_details": [
                    {
                        "id": str(listing_id),
                        "price": int(price),
                        "quantity": quantity,
                        "name": f"Telur grade {listing['grade']}"
                    }
                ]
            }

            try:
                resp = requests.post(
                    url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "Authorization": f"Basic {auth_str}",
                    },
                    timeout=10
                )
                if 200 <= resp.status_code < 300:
                    data_mid = resp.json()
                    snap_token = data_mid.get("token")

                    # Simpan token ke orders.midtrans_transaction_id (opsional)
                    cur2 = conn.cursor()
                    cur2.execute(
                        "UPDATE orders SET midtrans_transaction_id = %s WHERE id = %s",
                        (snap_token, order_db_id)
                    )
                    conn.commit()
                    cur2.close()
                else:
                    print("Midtrans HTTP error:", resp.status_code, resp.text)
            except Exception as e:
                print("Midtrans request error:", e)
        else:
            print("MIDTRANS_SERVER_KEY tidak di-set, skip panggilan Snap (mode lokal).")

        # 9) Response ke frontend
        if is_json:
            return jsonify(
                success=True,
                snap_token=snap_token,
                order_id=order_id_str,
                message=None if snap_token else "Order dibuat tanpa Snap (cek konfigurasi Midtrans / mode lokal)."
            )
        else:
            if snap_token:
                flash("Order berhasil dibuat, silakan lanjutkan pembayaran.", "success")
            else:
                flash("Order berhasil dibuat tanpa Snap (mode lokal).", "success")
            return redirect(url_for('eggmart_controller.eggmartDetail', seller_id=seller_id))

    except mysql.connector.Error as e:
        conn.rollback()
        print("create_transaction DB error:", e)
        if is_json:
            return jsonify(success=False, message="Error database."), 500
        flash("Terjadi kesalahan di database.", "error")
        return redirect(url_for('eggmart_controller.eggmartDetail', seller_id=seller_id or 0))
    finally:
        conn.close()

@eggmart_controller.route('/dashboard')
@login_required
def eggmartDashboard():
    """
    Dashboard EggMart untuk PENGUSAHA / ADMIN:
    - Telur ready per grade (egg_scans)
    - Listing aktif (egg_listings)
    - Kartu statistik hari ini
    - Line chart penjualan 7 hari
    - Kategori terlaris per grade 30 hari
    - Transaksi terbaru
    - Daftar chat + isi chat + performa chat
    """
    now = datetime.now()

    available_by_grade = {}
    listings = []

    # Kartu statistik
    cards = {
        'today': {
            'sold_eggs': 0,        # total butir terjual hari ini
            'completed_orders': 0  # order selesai hari ini
        }
    }

    # Rating toko
    store_rating = {'avg_rating': 0.0, 'total_reviews': 0}

    # Kategori terlaris (per grade)
    best_grades = []

    # Transaksi terbaru
    recent_orders = []

    # Chat dashboard
    chat_threads = []         # list sesi chat (untuk list di kanan)
    chat_response_rate = 0    # persen sesi yang sudah dibalas admin/seller
    total_unread_chats = 0    # total pesan belum dibaca

    # Data untuk line chart
    sales_chart_labels = []   # ['Mon', 'Tue', ...]
    sales_chart_data = []     # [10, 5, ...]

    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            seller_id = current_user.id

            # ==========================
            # 1) Telur ready (belum di-list) per grade
            # ==========================
            cur.execute("""
                SELECT grade, COUNT(*) AS qty
                FROM egg_scans
                WHERE user_id = %s
                  AND status = 'available'
                  AND (is_listed = FALSE OR is_listed IS NULL)
                GROUP BY grade
            """, (seller_id,))
            for row in cur.fetchall():
                available_by_grade[row["grade"]] = row["qty"]

            # ==========================
            # 2) Listing aktif milik seller ini
            # ==========================
            cur.execute("""
                SELECT id, grade, stock_eggs, price_per_egg, status
                FROM egg_listings
                WHERE seller_id = %s
                ORDER BY grade
            """, (seller_id,))
            for row in cur.fetchall():
                listings.append({
                    "id": row["id"],
                    "grade": row["grade"],
                    "stock": row["stock_eggs"],
                    "price": row["price_per_egg"],
                    "status": row["status"],
                })

            # ==========================
            # 3) Kartu statistik hari ini
            # ==========================
            today_start = datetime(now.year, now.month, now.day)
            today_end = today_start + timedelta(days=1)

            cur.execute("""
                SELECT 
                    COALESCE(SUM(oi.quantity), 0) AS eggs_sold,
                    COUNT(DISTINCT o.id) AS orders_completed
                FROM orders o
                JOIN order_items oi ON oi.order_id = o.id
                JOIN egg_scans es ON es.id = oi.egg_scan_id
                WHERE o.seller_id = %s
                  AND o.status IN ('paid','settlement')
                  AND o.created_at >= %s
                  AND o.created_at < %s
            """, (seller_id, today_start, today_end))
            row = cur.fetchone()
            if row:
                cards['today']['sold_eggs'] = int(row['eggs_sold'] or 0)
                cards['today']['completed_orders'] = int(row['orders_completed'] or 0)

            # ==========================
            # 4) Rating toko (semua waktu)
            # ==========================
            cur.execute("""
                SELECT 
                    COALESCE(AVG(rating), 0) AS avg_rating,
                    COUNT(*) AS total_reviews
                FROM seller_ratings
                WHERE seller_id = %s
            """, (seller_id,))
            row = cur.fetchone()
            if row:
                store_rating['avg_rating'] = float(row['avg_rating'] or 0)
                store_rating['total_reviews'] = int(row['total_reviews'] or 0)

            # ==========================
            # 5) Kategori terlaris (grade) 30 hari terakhir
            # ==========================
            start_30 = now - timedelta(days=30)
            cur.execute("""
                SELECT es.grade, COALESCE(SUM(oi.quantity), 0) AS qty
                FROM orders o
                JOIN order_items oi ON oi.order_id = o.id
                JOIN egg_scans es ON es.id = oi.egg_scan_id
                WHERE o.seller_id = %s
                  AND o.status IN ('paid','settlement')
                  AND o.created_at >= %s
                GROUP BY es.grade
            """, (seller_id, start_30))
            rows = cur.fetchall()
            total_qty = sum(r['qty'] for r in rows) or 0
            if total_qty == 0:
                total_qty = 1  # hindari bagi 0

            for r in rows:
                pct = round((r['qty'] / total_qty) * 100)
                best_grades.append({
                    'label': f"Grade {r['grade']}",
                    'grade': r['grade'],
                    'qty': int(r['qty']),
                    'percent': pct,
                })

            # ==========================
            # 6) Line chart penjualan 7 hari terakhir
            # ==========================
            start_7 = now - timedelta(days=6)             # 6 hari ke belakang + hari ini
            start_7_date = datetime(start_7.year, start_7.month, start_7.day)

            cur.execute("""
                SELECT DATE(o.created_at) AS d,
                       COALESCE(SUM(oi.quantity),0) AS qty
                FROM orders o
                JOIN order_items oi ON oi.order_id = o.id
                JOIN egg_scans es ON es.id = oi.egg_scan_id
                WHERE o.seller_id = %s
                  AND o.status IN ('paid','settlement')
                  AND o.created_at >= %s
                GROUP BY DATE(o.created_at)
                ORDER BY d
            """, (seller_id, start_7_date))
            data_by_date = {}
            for row in cur.fetchall():
                key = row['d'].strftime('%Y-%m-%d')
                data_by_date[key] = int(row['qty'] or 0)

            day_cursor = start_7_date
            for _ in range(7):
                key = day_cursor.strftime('%Y-%m-%d')
                label = day_cursor.strftime('%a')  # Mon, Tue, ...
                sales_chart_labels.append(label)
                sales_chart_data.append(data_by_date.get(key, 0))
                day_cursor += timedelta(days=1)

            # ==========================
            # 7) Transaksi terbaru (5 terakhir)
            # ==========================
            cur.execute("""
                SELECT 
                    o.id,
                    o.created_at,
                    o.status,
                    o.total,
                    u.name AS buyer_name,
                    COUNT(DISTINCT oi.egg_scan_id) AS eggs_count
                FROM orders o
                LEFT JOIN users u ON u.id = o.buyer_id
                LEFT JOIN order_items oi ON oi.order_id = o.id
                WHERE o.seller_id = %s
                GROUP BY o.id, o.created_at, o.status, o.total, u.name
                ORDER BY o.created_at DESC
                LIMIT 5
            """, (seller_id,))
            for row in cur.fetchall():
                recent_orders.append({
                    'id': row['id'],
                    'code': f"TRX{row['id']:03d}",
                    'buyer_name': row['buyer_name'] or 'Guest',
                    'eggs_count': int(row['eggs_count'] or 0),
                    'total': float(row['total'] or 0),
                    'status': row['status'],
                    'created_at': row['created_at'],
                })

            # ==========================
            # 8) Chat sessions khusus seller ini
            #     guest_email diset sebagai 'seller:{seller_id}'
            # ==========================
            seller_key = f"seller:{seller_id}"

            cur.execute("""
                SELECT 
                    cs.id,
                    cs.user_id AS buyer_id,
                    u.name AS buyer_name,
                    cs.status,
                    cs.last_message_at,
                    (
                        SELECT message
                        FROM chat_messages cm
                        WHERE cm.session_id = cs.id
                        ORDER BY cm.created_at DESC
                        LIMIT 1
                    ) AS last_message,
                    (
                        SELECT COUNT(*)
                        FROM chat_messages cm2
                        WHERE cm2.session_id = cs.id
                          AND cm2.status = 'unread'
                          AND cm2.message_type IN ('guest_to_admin', 'user_to_admin')
                    ) AS unread_count
                FROM chat_sessions cs
                LEFT JOIN users u ON u.id = cs.user_id
                WHERE cs.guest_email = %s
                ORDER BY cs.last_message_at DESC
                LIMIT 10
            """, (seller_key,))
            session_rows = cur.fetchall()

            for row in session_rows:
                name = row['buyer_name'] or f"Pembeli #{row['buyer_id'] or row['id']}"
                initials = ''.join([part[0].upper() for part in name.split()[:2]]) or 'PB'
                unread = int(row['unread_count'] or 0)
                total_unread_chats += unread

                chat_threads.append({
                    'id': row['id'],
                    'name': name,
                    'initials': initials,
                    'status': row['status'],
                    'last_message': row['last_message'] or '',
                    'last_time': row['last_message_at'],
                    'unread': unread,
                    # dipakai JS untuk fetch pesan (GET/POST)
                    'fetch_url': url_for('eggmart_controller.seller_chat_thread', session_id=row['id']),
                })

            # ==========================
            # 9) Performa chat (response rate) per seller
            # ==========================
            cur.execute("""
                SELECT COUNT(*) AS total_sessions
                FROM chat_sessions
                WHERE guest_email = %s
            """, (seller_key,))
            row = cur.fetchone()
            total_sessions = row['total_sessions'] or 0

            cur.execute("""
                SELECT COUNT(*) AS responded_sessions
                FROM chat_sessions cs
                WHERE cs.guest_email = %s
                  AND EXISTS (
                    SELECT 1
                    FROM chat_messages cm_g
                    WHERE cm_g.session_id = cs.id
                      AND cm_g.message_type IN ('guest_to_admin','user_to_admin')
                  )
                  AND EXISTS (
                    SELECT 1
                    FROM chat_messages cm_a
                    WHERE cm_a.session_id = cs.id
                      AND cm_a.message_type IN ('admin_to_guest','admin_to_user')
                  )
            """, (seller_key,))
            row = cur.fetchone()
            responded_sessions = row['responded_sessions'] or 0

            if total_sessions > 0:
                chat_response_rate = round(responded_sessions * 100 / total_sessions)

            cur.close()
        finally:
            conn.close()

    # Render ke template
    return render_template(
        'eggmart/index.html',
        active_menu="dashboard",
        now=now,
        available_by_grade=available_by_grade,
        listings=listings,
        cards=cards,
        store_rating=store_rating,
        best_grades=best_grades,
        recent_orders=recent_orders,
        chat_threads=chat_threads,
        chat_response_rate=chat_response_rate,
        total_unread_chats=total_unread_chats,
        sales_chart_labels=sales_chart_labels,
        sales_chart_data=sales_chart_data,
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
        return redirect(url_for('eggmart_controller.eggmartDashboard'))

    conn = get_db_connection()
    if not conn:
        flash('Gagal terhubung ke database.', 'error')
        return redirect(url_for('eggmart_controller.eggmartDashboard'))

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
            return redirect(url_for('eggmart_controller.eggmartDashboard'))

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

    return redirect(url_for('eggmart_controller.eggmartDashboard'))

# ==============================================================================
# 1. FUNGSI KATALOG DENGAN FILTER (YANG SEBELUMNYA SALAH/KURANG)
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

# Di dalam file eggmart_controller.py

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
# 2. FUNGSI BARU: API UPDATE PROFILE (YANG HILANG)
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
# API CHAT BUYER <-> SELLER
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

        # Cari session antara buyer ini dan seller ini
        # Kita pakai guest_email sebagai 'kunci' seller: seller:<seller_id>
        cur.execute("""
            SELECT id
            FROM chat_sessions
            WHERE user_id = %s
              AND guest_email = %s
            LIMIT 1
        """, (buyer_id, f"seller:{seller_id}"))
        row = cur.fetchone()

        if row:
            session_id = row['id']
        else:
            # Belum ada session → buat baru
            cur.execute("""
                INSERT INTO chat_sessions (user_id, guest_email, guest_name, status, last_message_at, created_at)
                VALUES (%s, %s, %s, 'active', NOW(), NOW())
            """, (buyer_id, f"seller:{seller_id}", seller['name']))
            session_id = cur.lastrowid
            conn.commit()

        # Ambil semua pesan chat utk session ini
        cur.execute("""
            SELECT message, message_type, created_at
            FROM chat_messages
            WHERE session_id = %s
            ORDER BY created_at ASC
        """, (session_id,))
        msgs = []
        for m in cur.fetchall():
            mtype = m['message_type']
            # Dari sudut pandang BUYER:
            # - user_to_admin / guest_to_admin = pesan dari buyer
            # - admin_to_user / admin_to_guest = pesan dari seller
            if mtype in ('user_to_admin', 'guest_to_admin'):
                sender = 'self'
            else:
                sender = 'seller'

            msgs.append({
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

        # Cari / buat session
        cur.execute("""
            SELECT id
            FROM chat_sessions
            WHERE user_id = %s
              AND guest_email = %s
            LIMIT 1
        """, (buyer_id, f"seller:{seller_id}"))
        row = cur.fetchone()

        if row:
            session_id = row['id']
        else:
            cur.execute("""
                INSERT INTO chat_sessions (user_id, guest_email, guest_name, status, last_message_at, created_at)
                VALUES (%s, %s, %s, 'active', NOW(), NOW())
            """, (buyer_id, f"seller:{seller_id}", seller['name']))
            session_id = cur.lastrowid

        # Insert pesan (buyer -> seller)
        cur.execute("""
            INSERT INTO chat_messages (
                session_id, user_id, message, message_type, status, created_at
            )
            VALUES (%s, %s, %s, 'user_to_admin', 'unread', NOW())
        """, (session_id, buyer_id, text))

        # Update last_message_at session
        cur.execute("""
            UPDATE chat_sessions
            SET last_message_at = NOW()
            WHERE id = %s
        """, (session_id,))

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

@eggmart_controller.route('/history')
@login_required
def eggmartHistory():
    """
    Halaman riwayat transaksi:
    - Auto-expire order lama
    - Fetch history
    """
    now = datetime.now()
    buyer_orders = []
    seller_orders = [] # (Keep empty if not used, or implement logic if needed for seller view)

    conn = get_db_connection()
    if not conn:
        flash("Gagal koneksi ke database.", "error")
        return redirect(url_for('eggmart_controller.eggmart'))

    try:
        cur = conn.cursor(dictionary=True)

        # 1. AUTO-EXPIRE LOGIC (Lazy Update)
        # Jika order masih 'pending' tapi sudah lebih dari 1 jam (atau sesuaikan dengan expiry Midtrans),
        # ubah status menjadi 'expire' di database lokal agar tidak menggantung selamanya.
        expiry_time = now - timedelta(hours=1) 
        cur.execute("""
            UPDATE orders 
            SET status = 'expire' 
            WHERE status = 'pending' AND created_at < %s
        """, (expiry_time,))
        conn.commit()

        # 2. FETCH HISTORY
        # Added: o.midtrans_transaction_id as snap_token
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

        # 3. Fetch Items Details (Optimization)
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
                
                # Generate Description
                grade_counts = {}
                for i in r_items:
                    g = i['grade']
                    grade_counts[g] = grade_counts.get(g, 0) + i['quantity']
                desc_parts = [f"Grade {g} ({q}x)" for g, q in grade_counts.items()]
                
                buyer_orders.append({
                    "id": r['id'],
                    "code": r['midtrans_order_id'],
                    "snap_token": r['snap_token'], # Penting untuk tombol Bayar
                    "seller_name": r['farm_name'] or r['seller_name'],
                    "location": r['farm_location'],
                    "total": float(r['total'] or 0),
                    "status": r['status'], # pending, settlement, capture, expire, cancel
                    "date": r['created_at'],
                    "total_qty": int(r['total_eggs'] or 0),
                    "description": ", ".join(desc_parts),
                    "items": r_items
                })

        cur.close()
    except mysql.connector.Error as e:
        print("History DB Error:", e)
    finally:
        conn.close()

    # Cek jika ada new_order_code untuk menampilkan invoice otomatis
    new_order_code = request.args.get('new_order_code')
    new_order_data = next((o for o in buyer_orders if o['code'] == new_order_code), None)

    return render_template(
        'eggmart/history.html',
        orders=buyer_orders,
        new_order=new_order_data,
        active_menu='history',
        # Kirim Client Key untuk Snap JS
        midtrans_client_key=current_app.config.get("MIDTRANS_CLIENT_KEY") 
    )

    

@eggmart_controller.route('/seller-chat/<int:session_id>', methods=['GET', 'POST'])
@login_required
def seller_chat_thread(session_id):
    """
    API chat untuk PENJUAL di dashboard.
    GET  -> ambil semua pesan di sesi ini
    POST -> kirim balasan dari penjual
    """
    # Boleh kamu ganti logic role, tapi minimal pastikan bukan guest
    if current_user.role not in ('pengusaha', 'admin'):
        return jsonify(success=False, message="Hanya penjual yang dapat mengakses chat ini."), 403

    conn = get_db_connection()
    if not conn:
        return jsonify(success=False, message="Gagal koneksi database."), 500

    try:
        cur = conn.cursor(dictionary=True)

        seller_key = f"seller:{current_user.id}"

        # Pastikan sesi chat milik seller ini
        cur.execute("""
            SELECT cs.id, cs.user_id AS buyer_id, u.name AS buyer_name
            FROM chat_sessions cs
            LEFT JOIN users u ON u.id = cs.user_id
            WHERE cs.id = %s
              AND cs.guest_email = %s
        """, (session_id, seller_key))
        sess = cur.fetchone()

        if not sess:
            return jsonify(success=False, message="Sesi chat tidak ditemukan."), 404

        # ===================== GET: ambil pesan =====================
        if request.method == 'GET':
            cur.execute("""
                SELECT id, message, message_type, status, created_at
                FROM chat_messages
                WHERE session_id = %s
                ORDER BY created_at ASC
            """, (session_id,))
            rows = cur.fetchall()

            messages = []
            unread_ids = []
            for row in rows:
                mtype = row["message_type"]
                if mtype in ("user_to_admin", "guest_to_admin"):
                    sender = "buyer"
                    if row["status"] == "unread":
                        unread_ids.append(row["id"])
                else:
                    sender = "seller"

                messages.append({
                    "sender": sender,   # 'buyer' atau 'seller'
                    "text": row["message"],
                    "time": row["created_at"].strftime("%H:%M") if row["created_at"] else ""
                })

            # tandai pesan buyer sebagai 'read'
            if unread_ids:
                placeholders = ",".join(["%s"] * len(unread_ids))
                cur.execute(f"""
                    UPDATE chat_messages
                    SET status = 'read'
                    WHERE id IN ({placeholders})
                """, unread_ids)
                conn.commit()

            buyer_name = sess["buyer_name"] or f"Pembeli #{sess['buyer_id'] or session_id}"

            return jsonify(
                success=True,
                session_id=session_id,
                buyer_name=buyer_name,
                messages=messages
            )

        # ===================== POST: kirim balasan seller =====================
        data = request.get_json(silent=True) or {}
        text = (data.get("message") or "").strip()
        if not text:
            return jsonify(success=False, message="Pesan tidak boleh kosong."), 400

        # Insert pesan dari penjual
        cur.execute("""
            INSERT INTO chat_messages (
                session_id, user_id, message, message_type, status, created_at
            )
            VALUES (%s, %s, %s, 'admin_to_user', 'unread', NOW())
        """, (session_id, current_user.id, text))

        # Update last_message_at session
        cur.execute("""
            UPDATE chat_sessions
            SET last_message_at = NOW()
            WHERE id = %s
        """, (session_id,))
        conn.commit()

        now_time = datetime.now().strftime("%H:%M")

        return jsonify(
            success=True,
            message={
                "sender": "seller",
                "text": text,
                "time": now_time
            }
        )

    except mysql.connector.Error as e:
        conn.rollback()
        print("seller_chat_thread error:", e)
        return jsonify(success=False, message="Kesalahan database."), 500
    finally:
        conn.close()

