# controllers/eggmonitor_controller.py
from flask import Blueprint, render_template, request, url_for, redirect, flash, current_app, session
from flask_login import login_required, current_user
from utils.dashboard_data import build_dashboard_data
from utils.report_data import build_report_data
from utils.user_data import build_user_data
from utils.ml_utils import predict_image
from utils.database import get_db_connection
import os
import mysql.connector
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
