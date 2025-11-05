from flask import Flask, render_template
import math
from datetime import datetime

app = Flask(__name__)

def build_dashboard_data():
    # --- Header ---
    header = {
        "user_name": "Dio Aranda",
        "egg_vision_count": 10,
        "location": "Klari, Karawang",
        "device": "EggVision 01",
        # waktu awal (akan di-update di client oleh JS per detik)
        "date_str": datetime.now().strftime("%d/%b/%Y"),
        "time_str": datetime.now().strftime("%H:%M:%S"),
        "avatar_seed": "dio"
    }

    # --- Notifications ---
    notifications = [
        {"id": "1", "message": "12 telur busuk terdeteksi pukul 08:30"},
        {"id": "2", "message": "12 telur busuk terdeteksi pukul 08:30"},
    ]

    # --- Grades / Donut chart ---
    # warna hex sederhana untuk menggantikan token Tailwind kustom
    grades = [
        {"label": "Grade I", "count": 785, "percentage": 61, "color": "#4f46e5"},  # indigo-600
        {"label": "Grade II", "count": 342, "percentage": 27, "color": "#22c55e"}, # green-500
        {"label": "Grade III", "count": 117, "percentage": 9,  "color": "#f59e0b"}, # amber-500
        {"label": "Reject (retak/busuk)", "count": 40, "percentage": 3, "color": "#ef4444"}, # red-500
    ]
    total = sum(g["count"] for g in grades)

    # hitung geometry donut (r=70, sama seperti di React)
    r = 70
    circumference = 2 * math.pi * r
    acc_pct = 0.0
    for i, g in enumerate(grades):
        g["dash"] = g["percentage"] / 100.0 * circumference
        g["gap"] = circumference - g["dash"]
        # rotasi start -90deg + akumulasi sebelumnya
        g["rotation"] = -90.0 + (acc_pct * 360.0 / 100.0)
        acc_pct += g["percentage"]

    # --- Status Panel ---
    status_items = [
        {
            "id": "eggvision", "label": "Turn On EggVision",
            "is_on": True, "variant": "success", "sub_items": []
        },
        {
            "id": "loadcell", "label": "Load Cell",
            "is_on": True, "variant": "success", "sub_items": []
        },
        {
            "id": "vision", "label": "Vision Camera",
            "is_on": False, "variant": "danger",
            "sub_items": [
                {"label": "Klasifikasi Warna", "is_on": False},
                {"label": "Pengolahan Citra", "is_on": False},
                {"label": "Estimasi Masa Simpan", "is_on": False},
            ]
        },
        {
            "id": "conveyor", "label": "Konveyor",
            "is_on": True, "variant": "default",
            "sub_items": [
                {"label": "Jalur Kanan EggVision", "is_on": True},
                {"label": "Jalur Tengah EggVision", "is_on": True},
                {"label": "Jalur Kiri EggVision", "is_on": True},
            ]
        },
    ]

    # --- Data Table ---
    records = [
        {
            "no": 1, "idNumerik": "2025101901", "tanggal": "16/Oct/2025 16:55:15",
            "ketebalan": "Sedang", "kebersihan": "Bersih", "keutuhan": "Utuh",
            "kesegaran": "Segar", "beratTelur": "50.2 gram"
        },
        {
            "no": 2, "idNumerik": "2025101902", "tanggal": "16/Oct/2025 16:54:15",
            "ketebalan": "Tipis", "kebersihan": "Bersih", "keutuhan": "Retak",
            "kesegaran": "Segar", "beratTelur": "55 gram"
        },
        {
            "no": 3, "idNumerik": "2025101903", "tanggal": "16/Oct/2025 16:53:15",
            "ketebalan": "Tebal", "kebersihan": "Cukup Bersih", "keutuhan": "Utuh",
            "kesegaran": "Segar", "beratTelur": "65 gram"
        },
        {
            "no": 4, "idNumerik": "2025101904", "tanggal": "16/Oct/2025 16:54:15",
            "ketebalan": "Tebal", "kebersihan": "Tidak Bersih", "keutuhan": "Utuh",
            "kesegaran": "Busuk", "beratTelur": "67.5 gram"
        },
        {
            "no": 5, "idNumerik": "2025101905", "tanggal": "16/Oct/2025 16:54:15",
            "ketebalan": "Tipis", "kebersihan": "Cukup Bersih", "keutuhan": "Retak",
            "kesegaran": "Busuk", "beratTelur": "55.4 gram"
        },
    ]

    return {
        "header": header,
        "notifications": notifications,
        "grades": grades,
        "grades_total": total,
        "donut_r": r,
        "donut_circ": circumference,
        "status_items": status_items,
        "records": records,
        "table_meta": {
            "total_records": "1,500 records",
            "rows_shown": 5
        }
    }

@app.route("/")
def index():
    data = build_dashboard_data()
    return render_template("index.html", **data)


def build_report_data():
    header = {
        "user_name": "Dio Aranda",
        "egg_vision_count": 10,
        "location": "Klari, Karawang",
        "device": "EggVision 01",
        "date_str": datetime.now().strftime("%d/%b/%Y"),
        "time_str": datetime.now().strftime("%H:%M:%S"),
        "avatar_seed": "dio"
    }

    # Data tabel (tambahkan kolom Kategori Mutu, Parameter, Keterangan)
    records = [
        {"no":1,"idNumerik":"2025101901","tanggal":"16/Oct/2025 16:55:15","ketebalan":"Sedang","kebersihan":"Bersih","keutuhan":"Utuh","kesegaran":"Segar","beratTelur":"50.2 gram","kategori":"Grade III","parameter":"Tidak Cacat","keterangan":"Sempurna"},
        {"no":2,"idNumerik":"2025101902","tanggal":"16/Oct/2025 16:54:15","ketebalan":"Tipis","kebersihan":"Bersih","keutuhan":"Retak","kesegaran":"Segar","beratTelur":"55 gram","kategori":"Reject","parameter":"Ketebalan","keterangan":"Kulit Terlalu Tipis"},
        {"no":3,"idNumerik":"2025101903","tanggal":"16/Oct/2025 16:53:15","ketebalan":"Tebal","kebersihan":"Cukup Bersih","keutuhan":"Utuh","kesegaran":"Segar","beratTelur":"65 gram","kategori":"Grade III","parameter":"Kebersihan","keterangan":"Noda Melebihi Batas"},
        {"no":4,"idNumerik":"2025101904","tanggal":"16/Oct/2025 16:52:15","ketebalan":"Tebal","kebersihan":"Tidak Bersih","keutuhan":"Utuh","kesegaran":"Busuk","beratTelur":"67.5 gram","kategori":"Grade III","parameter":"Ketebalan","keterangan":"Berat Sedang"},
        {"no":5,"idNumerik":"2025101905","tanggal":"16/Oct/2025 16:51:15","ketebalan":"Tipis","kebersihan":"Cukup Bersih","keutuhan":"Retak","kesegaran":"Busuk","beratTelur":"55.4 gram","kategori":"Reject","parameter":"Berat","keterangan":"Berat Kecil"},
    ]
    table_meta = {"total_records": "1,500 records", "rows_shown": 5}

    # Grafik histogram (dummy 12 bar)
    hist_labels = [f"S{i+1}" for i in range(12)]
    hist_values = [240, 420, 180, 260, 120, 460, 380, 210, 160, 430, 250, 360]

    # Ringkasan kategori mutu
    grade_summary = [
        {"id":"grade1", "label":"Grade I", "count":198},
        {"id":"grade2", "label":"Grade II", "count":76},
        {"id":"grade3", "label":"Grade III", "count":85},
        {"id":"reject", "label":"Reject", "count":10},
    ]
    total_butir = sum(g["count"] for g in grade_summary)
    for g in grade_summary:
        g["pct"] = 0 if total_butir == 0 else round(g["count"]*100/total_butir,1)

    return {
        "active_menu": "laporan",
        "header": header,
        "records": records,
        "table_meta": table_meta,
        "hist_labels": hist_labels,
        "hist_values": hist_values,
        "grade_summary": grade_summary,
        "total_butir": total_butir
    }

@app.route("/laporan")
def laporan():
    data = build_report_data()
    return render_template("laporan.html", **data)

def build_landing_data():
    # konten dummy – bebas kamu ganti
    products = [
        {"title": "EggMart", "description": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."},
        {"title": "EggVision", "description": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."},
        {"title": "EggMonitor", "description": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."},
    ]
    showcases = [
        {"title": "Lorem Ipsum", "description": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.", "imageLeft": True},
        {"title": "Lorem Ipsum", "description": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.", "imageLeft": False},
    ]
    features = [
        {"title": "Lorem Ipsum", "description": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."},
        {"title": "Lorem Ipsum", "description": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."},
        {"title": "Lorem Ipsum", "description": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."},
    ]
    return {
        "products": products,
        "showcases": showcases,
        "features": features,
    }

@app.route("/landing")
def landing():
    data = build_landing_data()
    return render_template("landing.html", **data)



# --- Profile / Settings data ---
def build_user_data():
    settings_items = [
        {"icon": "key", "title": "Account", "desc": "Perbarui kredensial & info akun"},
        {"icon": "lock", "title": "Privacy", "desc": "Preferensi privasi & keamanan"},
        {"icon": "palette", "title": "Tema", "desc": "Light/Dark & warna aksen"},
        {"icon": "bell", "title": "Notifikasi", "desc": "Pengaturan pesan notifikasi"},
        {"icon": "keyboard", "title": "Pintasan Keyboard", "desc": "Navigasi cepat"},
        {"icon": "help-circle", "title": "Pusat Bantuan", "desc": "FAQ, kontak, kebijakan"},
    ]
    
    return {
        "user": {
            "name": "Dio Aranda",
            "tagline": "Giving up is an not option",
            "avatar_seed": "Dio",
            "phone_display": "+62 813-1777-3184",
            "phone_raw": "+6281317773184",
        },
        "settings_items": settings_items,
        
        
    }

@app.route("/profile")
def profile():
    return render_template("profile.html", **build_user_data(), active_menu="profile")

@app.route("/settings")
def settings():
    # daftar item settings (ikon hanya dipakai di HTML)
    settings_items = [
        {"icon": "key", "title": "Account", "desc": "Perbarui kredensial & info akun"},
        {"icon": "lock", "title": "Privacy", "desc": "Preferensi privasi & keamanan"},
        {"icon": "palette", "title": "Tema", "desc": "Light/Dark & warna aksen"},
        {"icon": "bell", "title": "Notifikasi", "desc": "Pengaturan pesan notifikasi"},
        {"icon": "keyboard", "title": "Pintasan Keyboard", "desc": "Navigasi cepat"},
        {"icon": "help-circle", "title": "Pusat Bantuan", "desc": "FAQ, kontak, kebijakan"},
    ]
    return render_template("settings.html",
                           **build_user_data(),
                           active_menu="settings")




if __name__ == "__main__":
    app.run(debug=True)
