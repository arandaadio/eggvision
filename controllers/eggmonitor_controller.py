# controllers/eggmonitor_controller.py
import json
from flask import Blueprint, render_template, request, url_for, redirect, flash, current_app, session, jsonify
from flask_login import login_required, current_user
from utils.dashboard_data import build_dashboard_data
from utils.report_data import build_report_data
from utils.user_data import build_user_data
from utils.ml_utils import predict_image
from utils.database import get_db_connection
import os
import mysql.connector
import paho.mqtt.client as mqtt
from werkzeug.utils import secure_filename

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

    # Ambil hasil scan terakhir dari session (sekali pakai, kayak with() Laravel)
    last_scan = session.pop('last_scan', None)
    if last_scan:
        data.update(
            uploaded_image = url_for('static', filename=last_scan["image_path"]),
            prediction     = last_scan["prediction"],
            confidence     = last_scan["confidence"],
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
    prediction_display = f"Grade {grade} · {keutuhan_pred or '-'} · {color_pred or '-'}"

    session["last_scan"] = {
        "image_path": f"uploads/{filename}",
        "prediction": prediction_display,
        "confidence": f"{grade_conf:.2f}%",
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


@eggmonitor_controller.route('/profile')
@login_required
def eggmonitor_profile():
    if current_user.role != 'pengusaha':
        flash('Hanya Pengusaha yang dapat mengakses EggMonitor.', 'error')
        return redirect(url_for('comprof_controller.comprof_beranda'))

    data = build_user_data()
    return render_template('eggmonitor/profile.html', **data, active_menu="profile")


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
