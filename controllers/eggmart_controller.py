from flask import Blueprint, render_template, flash, redirect, url_for, request, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime
import mysql.connector

from utils.db import get_db_connection  # sesuaikan
import midtransclient   # <-- penting


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



@eggmart_controller.route('/checkout', methods=['POST'])
@login_required
def create_transaction():
    """
    Endpoint checkout:
    - Input: listing_id, quantity
    - Validasi stok
    - Insert ke egg_orders
    - Panggil Midtrans Snap
    """

    # Bisa JSON (fetch) atau form (fallback)
    if request.is_json:
        data = request.get_json() or {}
        listing_id = data.get('listing_id')
        quantity = data.get('quantity')
    else:
        listing_id = request.form.get('listing_id')
        quantity = request.form.get('quantity')

    try:
        listing_id = int(listing_id)
        quantity = int(quantity)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Data tidak valid."}), 400

    if quantity <= 0:
        return jsonify({"success": False, "message": "Jumlah harus lebih dari 0."}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "message": "Koneksi database gagal."}), 500

    try:
        cur = conn.cursor(dictionary=True)

        # 1) Ambil listing
        cur.execute("""
            SELECT el.id, el.seller_id, el.grade, el.stock_eggs, el.price_per_egg, el.status,
                   u.name AS seller_name
            FROM egg_listings el
            JOIN users u ON u.id = el.seller_id
            WHERE el.id = %s
            LIMIT 1
        """, (listing_id,))
        listing = cur.fetchone()

        if not listing or listing["status"] != "active":
            return jsonify({"success": False, "message": "Listing tidak ditemukan atau tidak aktif."}), 404

        if quantity > listing["stock_eggs"]:
            return jsonify({"success": False, "message": f"Stok tidak cukup (maks {listing['stock_eggs']} butir)."}), 400

        price_per_egg = int(listing["price_per_egg"])
        gross_amount = price_per_egg * quantity

        # 2) Generate order_code (juga dipakai sebagai midtrans_order_id)
        order_code = f"EGG-{listing_id}-{int(datetime.now().timestamp())}"

        # 3) Insert ke egg_orders (SUDAH ada listing_id & grade)
        cur.execute("""
            INSERT INTO egg_orders (
                order_code, buyer_id, seller_id, listing_id,
                grade, quantity, price_per_egg, total_amount,
                midtrans_order_id, status, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, NOW(), NOW()
            )
        """, (
            order_code,              # order_code
            current_user.id,         # buyer_id
            listing["seller_id"],    # seller_id
            listing["id"],           # listing_id
            listing["grade"],        # grade (ambil dari egg_listings)
            quantity,                # quantity
            price_per_egg,           # price_per_egg
            gross_amount,            # total_amount
            order_code,              # midtrans_order_id
            "pending",               # status
        ))
        conn.commit()

        # 4) Panggil Midtrans Snap
        snap = get_midtrans_snap()

        customer_details = {
            "first_name": current_user.name,
            "email": getattr(current_user, 'email', None) or "no-email@example.com",
            "phone": getattr(current_user, 'phone', None) or "08123456789",
        }

        item_details = [{
            "id": str(listing["id"]),
            "price": price_per_egg,
            "quantity": quantity,
            "name": f"Telur Grade {listing['grade']}",
        }]

        transaction_params = {
            "transaction_details": {
                "order_id": order_code,
                "gross_amount": gross_amount,
            },
            "item_details": item_details,
            "customer_details": customer_details,
        }

        snap_response = snap.create_transaction(transaction_params)
        snap_token = snap_response.get("token")

        if not snap_token:
            return jsonify({"success": False, "message": "Gagal mendapatkan Snap token."}), 500

        # 5) Simpan snap_token ke egg_orders
        cur.execute("""
            UPDATE egg_orders
            SET midtrans_snap_token = %s, updated_at = NOW()
            WHERE order_code = %s
        """, (snap_token, order_code))
        conn.commit()

        return jsonify({
            "success": True,
            "snap_token": snap_token,
            "order_id": order_code,
        })

    except Exception as e:
        print("Midtrans checkout error:", e)
        conn.rollback()
        return jsonify({"success": False, "message": "Terjadi kesalahan server."}), 500
    finally:
        conn.close()



@eggmart_controller.route('/dashboard')
@login_required
def eggmartDashboard():
    """
    Dashboard EggMart untuk PENGUSAHA:
    - lihat telur ready (dari egg_scans)
    - kelola listing (harga & stok per grade)
    """
    # if current_user.role != 'pengusaha':
    #     flash('Dashboard EggMart hanya untuk pengusaha.', 'error')
    #     return redirect(url_for('comprof_controller.comprof_beranda'))

    now = datetime.now()
    available_by_grade = {}   # grade -> jumlah butir ready (belum di-list)
    listings = []             # listing aktif milik pengusaha

    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor(dictionary=True)

            # 1) Hitung telur ready dari hasil scan (belum di-list)
            cur.execute("""
                SELECT grade, COUNT(*) AS qty
                FROM egg_scans
                WHERE user_id = %s
                  AND status = 'available'
                  AND (is_listed = FALSE OR is_listed IS NULL)
                GROUP BY grade
            """, (current_user.id,))
            for row in cur.fetchall():
                available_by_grade[row["grade"]] = row["qty"]

            # 2) Ambil semua listing milik pengusaha ini
            cur.execute("""
                SELECT id, grade, stock_eggs, price_per_egg, status
                FROM egg_listings
                WHERE seller_id = %s
                ORDER BY grade
            """, (current_user.id,))
            for row in cur.fetchall():
                listings.append({
                    "id": row["id"],
                    "grade": row["grade"],
                    "stock": row["stock_eggs"],
                    "price": row["price_per_egg"],
                    "status": row["status"],
                })

            cur.close()
        finally:
            conn.close()

    return render_template(
        'eggmart/index.html',
        active_menu="dashboard",
        now=now,
        available_by_grade=available_by_grade,
        listings=listings,
    )
    
    
@eggmart_controller.route('/listing/save', methods=['POST'])
@login_required
def save_listing():
    """
    Pengusaha set / update harga & stok untuk grade tertentu.
    Stok diambil dari egg_scans (status available & belum di-list).
    """
    # if current_user.role != 'pengusaha':
    #     flash('Hanya pengusaha yang dapat mengelola listing.', 'error')
    #     return redirect(url_for('eggmart_controller.eggmartDashboard'))

    grade = (request.form.get('grade') or '').upper().strip()
    price = request.form.get('price')
    stock = request.form.get('stock')

    # Validasi basic
    if grade not in ('A', 'B', 'C'):
        flash('Grade tidak valid.', 'error')
        return redirect(url_for('eggmart_controller.eggmartDashboard'))

    try:
        price = int(price)
        stock = int(stock)
    except (TypeError, ValueError):
        flash('Harga dan stok harus berupa angka.', 'error')
        return redirect(url_for('eggmart_controller.eggmartDashboard'))

    if price <= 0 or stock <= 0:
        flash('Harga dan stok harus lebih dari 0.', 'error')
        return redirect(url_for('eggmart_controller.eggmartDashboard'))

    conn = get_db_connection()
    if not conn:
        flash('Koneksi database gagal.', 'error')
        return redirect(url_for('eggmart_controller.eggmartDashboard'))

    try:
        cur = conn.cursor(dictionary=True)

        # 1) Cek stok telur available dari hasil scan
        cur.execute("""
            SELECT COUNT(*) AS qty
            FROM egg_scans
            WHERE user_id = %s
              AND grade = %s
              AND status = 'available'
              AND (is_listed = FALSE OR is_listed IS NULL)
        """, (current_user.id, grade))
        row = cur.fetchone()
        available = row["qty"] if row else 0

        if stock > available:
            flash(f'Stok melebihi jumlah telur tersedia untuk grade {grade} (maks {available} butir).', 'error')
            return redirect(url_for('eggmart_controller.eggmartDashboard'))

        # 2) Cek apakah sudah ada listing aktif untuk grade ini
        cur.execute("""
            SELECT id
            FROM egg_listings
            WHERE seller_id = %s AND grade = %s AND status = 'active'
            LIMIT 1
        """, (current_user.id, grade))
        existing = cur.fetchone()

        if existing:
            # update listing existing
            cur.execute("""
                UPDATE egg_listings
                SET price_per_egg = %s,
                    stock_eggs = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (price, stock, existing["id"]))
        else:
            # insert listing baru
            cur.execute("""
                INSERT INTO egg_listings (
                    seller_id, grade, price_per_egg, stock_eggs, status, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, 'active', NOW(), NOW()
                )
            """, (current_user.id, grade, price, stock))

        # 3) Tandai sejumlah telur sebagai "listed"
        cur.execute("""
            UPDATE egg_scans
            SET is_listed = TRUE
            WHERE id IN (
                SELECT id FROM (
                    SELECT id
                    FROM egg_scans
                    WHERE user_id = %s
                      AND grade = %s
                      AND status = 'available'
                      AND (is_listed = FALSE OR is_listed IS NULL)
                    ORDER BY scanned_at ASC
                    LIMIT %s
                ) AS sub
            )
        """, (current_user.id, grade, stock))

        conn.commit()
        flash(f'Listing grade {grade} berhasil disimpan.', 'success')

    except mysql.connector.Error as e:
        print("save_listing error:", e)
        conn.rollback()
        flash('Terjadi kesalahan saat menyimpan listing.', 'error')
    finally:
        conn.close()

    # Laravel "redirect()->back()->with(...)" versi Flask:
    return redirect(url_for('eggmart_controller.eggmartDashboard'))


@eggmart_controller.route('/catalog')
@login_required
def eggmart():
    """EggMart catalog page (untuk PEMBELI)"""
    # kalau mau lock ke role pembeli, buka blok ini:
    # if current_user.role != 'pembeli':
    #     flash('Hanya Pembeli yang dapat mengakses EggMart.', 'error')
    #     return redirect(url_for('comprof_controller.comprof_beranda'))

    from datetime import datetime
    now = datetime.now()
    sellers = []

    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT 
                    u.id,
                    u.name,
                    u.farm_location,
                    COALESCE(AVG(r.rating), 0) AS rating,
                    COUNT(r.id) AS review_count
                FROM users u
                JOIN egg_listings el 
                    ON el.seller_id = u.id AND el.status = 'active'
                LEFT JOIN seller_ratings r 
                    ON r.seller_id = u.id
                WHERE u.role = 'pengusaha'
                GROUP BY u.id, u.name, u.farm_location
                ORDER BY u.name
            """)
            seller_rows = cur.fetchall()

            for row in seller_rows:
                code = (row["name"] or "SL")[:2].upper()

                cur2 = conn.cursor(dictionary=True)
                cur2.execute("""
                    SELECT 
                        id,
                        grade,
                        stock_eggs,
                        price_per_egg,
                        COALESCE(description, '') AS description
                    FROM egg_listings
                    WHERE seller_id = %s AND status = 'active'
                    ORDER BY grade
                """, (row["id"],))
                product_rows = cur2.fetchall()
                cur2.close()

                products = [
                    {
                        "id": p["id"],
                        "grade": p["grade"],
                        "stock": p["stock_eggs"],
                        "price": p["price_per_egg"],
                        "description": p["description"] or f"Telur grade {p['grade']} siap kirim",
                    }
                    for p in product_rows
                ]

                sellers.append(
                    {
                        "id": row["id"],
                        "code": code,
                        "name": row["name"],
                        "location": row["farm_location"] or "-",
                        "rating": float(row["rating"] or 0),
                        "review_count": row["review_count"],
                        "products": products,
                    }
                )

            cur.close()
        finally:
            conn.close()

    return render_template(
        "eggmart/catalog.html",
        sellers=sellers,
        active_menu="catalog",
        now=now,
    )


@eggmart_controller.route('/detail/<int:seller_id>')
@login_required
def eggmartDetail(seller_id):
    from datetime import datetime
    now = datetime.now()
    conn = get_db_connection()
    seller = None

    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT 
                    u.id,
                    u.name,
                    u.farm_location,
                    COALESCE(AVG(r.rating), 0) AS rating,
                    COUNT(r.id) AS review_count
                FROM users u
                LEFT JOIN seller_ratings r ON r.seller_id = u.id
                WHERE u.id = %s
                GROUP BY u.id, u.name, u.farm_location
            """, (seller_id,))
            row = cur.fetchone()
            if not row:
                flash("Penjual tidak ditemukan.", "error")
                return redirect(url_for("eggmart_controller.eggmart"))

            seller = {
                "id": row["id"],
                "code": (row["name"][:2] if row["name"] else "SL").upper(),
                "name": row["name"],
                "location": row["farm_location"] or "-",
                "rating": float(row["rating"] or 0),
                "review_count": row["review_count"],
            }

            cur.execute("""
                SELECT 
                    id,
                    grade,
                    stock_eggs,
                    price_per_egg,
                    COALESCE(description, '') AS description
                FROM egg_listings
                WHERE seller_id = %s AND status = 'active'
                ORDER BY grade
            """, (seller_id,))
            product_rows = cur.fetchall()

            seller["products"] = [
                {
                    "id": p["id"],
                    "grade": p["grade"],
                    "stock": p["stock_eggs"],
                    "price": p["price_per_egg"],
                    "description": p["description"] or f"Telur grade {p['grade']} siap kirim",
                }
                for p in product_rows
            ]

            cur.close()
        finally:
            conn.close()

    return render_template(
        "eggmart/catalog_detail.html",
        seller=seller,
        active_menu="catalog",
        now=now,
        midtrans_client_key=current_app.config.get("MIDTRANS_CLIENT_KEY")
    )
