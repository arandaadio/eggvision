# controllers/eggmonitor_controller.py
import json
from flask import Blueprint, render_template, request, url_for, redirect, flash, current_app, session, jsonify
from flask_login import login_required, current_user
from utils.dashboard_data import build_dashboard_data
from utils.report_data import build_report_data
from utils.user_data import build_user_data
from utils.ml_utils import predict_image
from utils.database import get_db_connection
from datetime import datetime, timedelta
import time
import os
import mysql.connector
import paho.mqtt.client as mqtt
from werkzeug.utils import secure_filename
from flask_login import logout_user


eggmonitor_controller = Blueprint('eggmonitor_controller', __name__)


@eggmonitor_controller.route('/')
@eggmonitor_controller.route('/index')
@login_required
def eggmonitor():
    """EggMonitor main dashboard - Pengusaha only"""
    if current_user.role != 'pengusaha':
        flash('Hanya Pengusaha yang dapat mengakses EggMonitor.', 'error')
        return redirect(url_for('comprof_controller.comprof_beranda'))

    data = build_dashboard_data(current_user.id)

    # --- FIX: Calculate Reject Count Separately ---
    conn = get_db_connection()
    reject_count = 0
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT COUNT(*) FROM egg_scans 
                WHERE user_id = %s AND grade = 'Reject'
            """, (current_user.id,))
            result = cur.fetchone()
            if result:
                reject_count = result[0]
        except Exception as e:
            print(f"Error fetching rejects: {e}")
        finally:
            conn.close()
    
    # Add to data context
    data['reject_count'] = reject_count
    
    # Update grades total to include rejects if not already
    # Assuming data['grades_total'] sums A+B+C, we add Rejects to it for the total scan count
    data['grades_total'] = data.get('grades_total', 0) + reject_count

    # Ambil hasil scan terakhir dari session (sekali pakai, kayak with() Laravel)
    last_scan = session.pop('last_scan', None)
    if last_scan:
        data.update(
            uploaded_image = url_for('static', filename=last_scan["image_path"]),
            prediction     = last_scan["prediction"],
            confidence     = last_scan["confidence"],
            scan_details   = last_scan.get("details", {})
        )

    # data sudah berisi header, grades, records, dll + (optional) hasil scan terakhir
    return render_template('eggmonitor/index.html', **data)

@eggmonitor_controller.route('/upload', methods=['POST'])
@login_required
def upload():
    """Upload gambar telur, prediksi grade (warna + keutuhan), simpan ke egg_scans"""
    if current_user.role != 'pengusaha':
        flash('Hanya Pengusaha yang dapat mengakses EggMonitor.', 'error')
        return redirect(url_for('comprof_controller.comprof_beranda'))

    if "file" not in request.files:
        flash('File gambar tidak ditemukan.', 'error')
        return redirect(url_for("eggmonitor_controller.eggmonitor"))

    file = request.files["file"]
    if file.filename == "":
        flash('Nama file kosong.', 'error')
        return redirect(url_for("eggmonitor_controller.eggmonitor"))

    filename = secure_filename(file.filename)
    file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    file.save(file_path)

    # ====== Prediksi gabungan (keutuhan + warna) ======
    grade, grade_conf, detail = predict_image(file_path)

    # detail: {"keutuhan": "...", "color": "...", ...}
    keutuhan_pred = detail.get("keutuhan")
    color_pred    = detail.get("color")

    # Simpan ke tabel egg_scans
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO egg_scans (
                    user_id,
                    numeric_id,
                    scanned_at,
                    ketebalan,
                    kebersihan,
                    keutuhan,
                    kesegaran,
                    berat_telur,
                    grade,
                    confidence,
                    image_path,
                    status,
                    is_listed
                ) VALUES (
                    %s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s,
                    'available', FALSE
                )
                """,
                (
                    current_user.id,
                    None,             # numeric_id
                    None,             # ketebalan
                    color_pred,       # sementara taruh warna di "kebersihan"
                    keutuhan_pred,    # keutuhan
                    None,             # kesegaran
                    None,             # berat_telur
                    grade,
                    grade_conf,
                    f"uploads/{filename}",
                )
            )
            conn.commit()
            cur.close()
        except mysql.connector.Error as e:
            print(f"Insert egg_scans error: {e}")
            flash("Terjadi kesalahan saat menyimpan data scan telur.", "error")
        finally:
            conn.close()

    # ====== Simpan hasil ke session untuk 1x tampilan di dashboard ======
    prediction_display = f"Grade {grade}"

    session["last_scan"] = {
        "image_path": f"uploads/{filename}",
        "prediction": prediction_display,
        "confidence": f"{grade_conf:.2f}%",
        "details": {
                "Ketebalan": detail.get("ketebalan", "-"),
                "Keutuhan": keutuhan_pred,
                "Kebersihan": color_pred, # Mapping color logic if needed, or use specific field
                "Kesegaran": detail.get("kesegaran", "-"),
                "Berat": detail.get("berat_telur", "-")
        }
    }

    flash("Scan telur berhasil disimpan.", "success")

    # PRG pattern: hindari resubmit kalau user tekan refresh
    return redirect(url_for("eggmonitor_controller.eggmonitor"))


@eggmonitor_controller.route('/laporan')
@login_required
def eggmonitor_laporan():
    if current_user.role != 'pengusaha':
        flash('Hanya Pengusaha yang dapat mengakses EggMonitor.', 'error')
        return redirect(url_for('comprof_controller.comprof_beranda'))

    data = build_report_data(current_user.id)
    return render_template('eggmonitor/laporan.html', **data)


@eggmonitor_controller.route('/seller')
@login_required
def eggmonitor_seller():
    """EggMart page (Seller page)"""
    if current_user.role != 'pengusaha':
        flash('Hanya Pengusaha yang dapat mengakses EggMart.', 'error')
        return redirect(url_for('comprof_controller.comprof_beranda'))

    # Dashboard EggMart untuk PENGUSAHA / ADMIN:
    # - Telur ready per grade (egg_scans)
    # - Listing aktif (egg_listings)
    # - Kartu statistik hari ini
    # - Line chart penjualan 7 hari
    # - Kategori terlaris per grade 30 hari
    # - Transaksi terbaru
    # - Daftar chat + isi chat + performa chat

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
            # 8) Chat sessions (UPDATED LOGIC)
            # ==========================
            # We look for sessions where seller_id matches current user
            cur.execute("""
                SELECT 
                    cs.id,
                    cs.user_id AS buyer_id,
                    u.name AS buyer_name,
                    cs.status,
                    cs.last_message_at,
                    cs.last_message,
                    (
                        SELECT COUNT(*)
                        FROM chat_messages cm2
                        WHERE cm2.session_id = cs.id
                          AND cm2.status = 'unread'
                          AND cm2.message_type = 'pembeli_to_pengusaha'
                    ) AS unread_count
                FROM chat_sessions cs
                LEFT JOIN users u ON u.id = cs.user_id
                WHERE cs.seller_id = %s
                ORDER BY cs.last_message_at DESC
                LIMIT 10
            """, (seller_id,))
            
            session_rows = cur.fetchall()

            for row in session_rows:
                name = row['buyer_name'] or f"Pembeli #{row['buyer_id']}"
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
                    # UPDATED URL HERE:
                    'fetch_url': url_for('eggmonitor_controller.seller_chat_thread', session_id=row['id']),
                })

            cur.close()
        finally:
            conn.close()

    return render_template(
        'eggmonitor/seller.html',
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
        active_menu="eggmart"
    )

#API endpoints to load and reply chats
@eggmonitor_controller.route('/api/chat/threads', methods=['GET'])
@login_required
def api_get_chat_threads():
    """
    API to fetch chat threads for the Seller Dashboard sidebar (AJAX Polling).
    """
    if current_user.role != 'pengusaha':
        return jsonify(success=False, threads=[])

    conn = get_db_connection()
    if not conn:
        return jsonify(success=False, message="Database error"), 500

    try:
        cur = conn.cursor(dictionary=True)
        
        # FIX: Use seller_id, not guest_email logic
        # FIX: Count unread messages specifically from 'pembeli_to_pengusaha'
        query = """
            SELECT 
                cs.id,
                cs.user_id AS buyer_id,
                u.name AS buyer_name,
                cs.status,
                cs.last_message_at,
                (
                    SELECT message 
                    FROM chat_messages 
                    WHERE session_id = cs.id 
                    ORDER BY created_at DESC LIMIT 1
                ) AS last_message,
                (
                    SELECT COUNT(*) 
                    FROM chat_messages 
                    WHERE session_id = cs.id 
                      AND status = 'unread' 
                      AND message_type = 'pembeli_to_pengusaha'
                ) AS unread_count
            FROM chat_sessions cs
            LEFT JOIN users u ON cs.user_id = u.id
            WHERE cs.seller_id = %s
            ORDER BY cs.last_message_at DESC
        """
        cur.execute(query, (current_user.id,))
        rows = cur.fetchall()

        results = []
        for row in rows:
            name = row['buyer_name'] or f"Pembeli #{row['buyer_id'] or row['id']}"
            initials = "".join([x[0] for x in name.split()[:2]]).upper()
            
            # Format Time
            time_str = ""
            if row['last_message_at']:
                time_str = row['last_message_at'].strftime('%H:%M')

            results.append({
                'id': row['id'],
                'name': name,
                'initials': initials,
                'status': row['status'],
                'last_message': row['last_message'] or '',
                'last_time': time_str,
                'unread': int(row['unread_count'] or 0),
                'fetch_url': url_for('eggmonitor_controller.seller_chat_thread', session_id=row['id'])
            })

        return jsonify(success=True, threads=results)

    except Exception as e:
        print(f"Error api_get_chat_threads: {e}")
        return jsonify(success=False, message=str(e)), 500
    finally:
        if conn:
            conn.close()


@eggmonitor_controller.route('/api/seller-chat/<int:session_id>', methods=['GET', 'POST'])
@login_required
def seller_chat_thread(session_id):
    """
    API for Seller to view thread and Reply.
    """
    if current_user.role != 'pengusaha':
        return jsonify(success=False, message="Unauthorized"), 403

    conn = get_db_connection()
    if not conn:
        return jsonify(success=False, message="DB Error"), 500

    try:
        cur = conn.cursor(dictionary=True)

        # Verify ownership (Seller must own this session)
        cur.execute("SELECT id, user_id FROM chat_sessions WHERE id=%s AND seller_id=%s", (session_id, current_user.id))
        session_row = cur.fetchone()
        
        if not session_row:
            return jsonify(success=False, message="Sesi tidak ditemukan"), 404

        # --- GET: Fetch Messages ---
        if request.method == 'GET':
            cur.execute("""
                SELECT id, message, message_type, created_at, status 
                FROM chat_messages 
                WHERE session_id = %s 
                ORDER BY created_at ASC
            """, (session_id,))
            rows = cur.fetchall()
            
            messages = []
            unread_ids = []
            
            for r in rows:
                # Identify sender for UI alignment
                if r['message_type'] == 'pengusaha_to_pembeli':
                    sender = 'seller'
                else:
                    sender = 'buyer'
                    # Only mark messages FROM buyer as read
                    if r['status'] == 'unread':
                        unread_ids.append(r['id'])
                
                messages.append({
                    'id': r['id'],
                    'sender': sender,
                    'text': r['message'],
                    'time': r['created_at'].strftime('%H:%M') if r['created_at'] else ''
                })
            
            # Mark messages as read (Batch Update)
            if unread_ids:
                placeholders = ','.join(['%s'] * len(unread_ids))
                # IMPORTANT: Only update status where id is in the list
                cur.execute(f"UPDATE chat_messages SET status='read' WHERE id IN ({placeholders})", tuple(unread_ids))
                conn.commit()
                
            return jsonify(success=True, messages=messages)

        # --- POST: Seller Reply ---
        if request.method == 'POST':
            data = request.get_json(silent=True) or {}
            text = data.get('message', '').strip()
            
            if not text:
                return jsonify(success=False, message="Pesan kosong"), 400
                
            # Insert message (Type: pengusaha_to_pembeli)
            cur.execute("""
                INSERT INTO chat_messages (session_id, user_id, message, message_type, status, created_at)
                VALUES (%s, %s, %s, 'pengusaha_to_pembeli', 'unread', NOW())
            """, (session_id, current_user.id, text))
            
            # Update session timestamp and snippet
            cur.execute("""
                UPDATE chat_sessions SET last_message=%s, last_message_at=NOW()
                WHERE id=%s
            """, (text, session_id))
            
            conn.commit()
            
            return jsonify(success=True, message={
                'sender': 'seller',
                'text': text,
                'time': datetime.now().strftime('%H:%M')
            })

    except Exception as e:
        print(f"Seller Chat Error: {e}")
        return jsonify(success=False, message="Server Error"), 500
    finally:
        conn.close()

@eggmonitor_controller.route('/profile')
@login_required
def eggmonitor_profile():
    if current_user.role != 'pengusaha':
        flash('Hanya Pengusaha yang dapat mengakses EggMonitor.', 'error')
        return redirect(url_for('comprof_controller.comprof_beranda'))

    data = build_user_data()
    return render_template('eggmonitor/profile.html', **data, active_menu="profile")

#profile edit function yah
@eggmonitor_controller.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    name = request.form.get('name')
    location = request.form.get('location')
    description = request.form.get('description')

    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            # Update user info in the database
            query = """
                UPDATE users 
                SET name = %s, farm_location = %s, farm_description = %s 
                WHERE id = %s
            """
            cur.execute(query, (name, location, description, current_user.id))
            conn.commit()
            flash('Profil berhasil diperbarui!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Gagal memperbarui profil: {e}', 'error')
        finally:
            cur.close()
            conn.close()
    
    # Redirects back to the page the user came from (dashboard or laporan)
    return redirect(request.referrer or url_for('eggmonitor_controller.dashboard'))

@eggmonitor_controller.route('/settings')
@login_required
def eggmonitor_settings():
    if current_user.role != 'pengusaha':
        flash('Hanya Pengusaha yang dapat mengakses EggMonitor.', 'error')
        return redirect(url_for('comprof_controller.comprof_beranda'))

    data = build_user_data()
    return render_template('eggmonitor/settings.html', **data, active_menu="settings")






MQTT_BROKER   = "broker.emqx.io"
MQTT_PORT     = 1883
MQTT_USERNAME = "emqx"
MQTT_PASSWORD = "public"

MQTT_TOPIC_EGG_COLOR = "emqx/esp32/eggcolor"   # ESP32 subscribe di sini
MQTT_TOPIC_CONTROL   = "emqx/esp32/control"    # ESP32 subscribe untuk manual LED

mqtt_client = mqtt.Client()
mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()  # jalan di background

# =========================
# ROUTE HALAMAN DETAIL ALAT
# =========================
@eggmonitor_controller.route("/detail")
def detail_alat():
    header = {
        "user_name": "Fauzi",
        "egg_vision_count": 3,
        "avatar_seed": "fauzi"
    }
    
    # URL Wokwi kamu
    wokwi_url = "https://wokwi.com/projects/448296525586142209?embed=1&view=diagram"

    return render_template(
        "eggmonitor/detail_alat.html",
        active_menu="detail",
        header=header,
        wokwi_url=wokwi_url
    )

# =========================
# API: warna telur dari kamera -> MQTT (otomatis)
# =========================
@eggmonitor_controller.route("/api/egg-color", methods=["POST"])
def api_egg_color():
    data = request.get_json() or {}
    label = data.get("label")

    if label not in ("lightbrown", "brown", "darkbrown"):
        return jsonify({"ok": False, "error": "invalid label"}), 400

    mqtt_client.publish(MQTT_TOPIC_EGG_COLOR, label, qos=0, retain=False)
    print("[MQTT eggcolor] ->", label)

    return jsonify({"ok": True, "label": label})

# =========================
# API: tombol kontrol LED manual -> MQTT
# =========================
@eggmonitor_controller.route("/api/wokwi/control", methods=["POST"])
def api_wokwi_control():
    data = request.get_json() or {}
    device = data.get("device")  # lightbrown / brown / darkbrown
    state  = data.get("state")   # on / off

    if device not in ("lightbrown", "brown", "darkbrown"):
        return jsonify({"ok": False, "error": "invalid device"}), 400

    if state not in ("on", "off"):
        return jsonify({"ok": False, "error": "invalid state"}), 400

    payload = json.dumps({"device": device, "state": state})
    mqtt_client.publish(MQTT_TOPIC_CONTROL, payload, qos=0, retain=False)
    print("[MQTT manual-led] ->", payload)

    return jsonify({"ok": True})
