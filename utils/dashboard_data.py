# utils/dashboard_data.py
from datetime import datetime
from utils.database import get_db_connection


def _build_header(user_id, total_scans):
    """Header untuk dashboard & laporan (nama user, lokasi, waktu, dll)."""
    conn = get_db_connection()
    user_name = "Pengusaha"
    location = "Lokasi belum di-set"

    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT name, farm_location FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            if row:
                user_name = row.get("name") or user_name
                if row.get("farm_location"):
                    location = row["farm_location"]
            cur.close()
        finally:
            conn.close()

    now = datetime.now()
    header = {
        "user_name": user_name,
        "avatar_seed": user_name,
        "egg_vision_count": total_scans,
        "device": "EggVision Device A",
        "location": location,
        "date_str": now.strftime("%d %b %Y"),
        "time_str": now.strftime("%H:%M"),
    }
    return header


def build_dashboard_data(user_id: int):
    """
    Bangun semua data untuk eggmonitor/index.html dari tabel egg_scans.
    """
    conn = get_db_connection()
    if not conn:
        # fallback kalau DB error
        header = _build_header(user_id, 0)
        return {
            "header": header,
            "grades": [],
            "grades_total": 0,
            "donut_r": 60,
            "notifications": [],
            "status_items": [],
            "table_meta": {"total_records": "0 data", "rows_shown": 0},
            "records": [],
            "active_menu": "dashboard",
        }

    try:
        cur = conn.cursor(dictionary=True)

        # Total scans untuk user ini
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM egg_scans WHERE user_id = %s",
            (user_id,),
        )
        total_scans = cur.fetchone()["cnt"]

        # Hitung jumlah tiap grade
        cur.execute(
            """
            SELECT grade, COUNT(*) AS cnt
            FROM egg_scans
            WHERE user_id = %s
            GROUP BY grade
            """,
            (user_id,),
        )
        grade_rows = cur.fetchall()
        grade_counts_raw = {row["grade"]: row["cnt"] for row in grade_rows}
        total_for_pct = sum(grade_counts_raw.values()) or 1  # avoid /0

        grade_defs = [
            ("A", "Grade A", "#22c55e"),
            ("B", "Grade B", "#eab308"),
            ("C", "Grade C", "#f97316"),
        ]

        grades = []
        start_angle = 0.0
        for code, label, color in grade_defs:
            cnt = grade_counts_raw.get(code, 0)
            pct = round(cnt * 100 / total_for_pct) if total_for_pct else 0

            # Donut param (sederhana saja, yang penting kebagi)
            dash = pct
            gap = 100 - dash
            rotation = start_angle
            start_angle += 360.0 * (cnt / total_for_pct) if total_for_pct else 0

            grades.append(
                {
                    "code": code,
                    "label": label,
                    "color": color,
                    "count": cnt,
                    "percentage": pct,
                    "dash": dash,
                    "gap": gap,
                    "rotation": rotation,
                }
            )

        donut_r = 60
        grades_total = sum(g["count"] for g in grades)

        # Notifikasi sederhana
        notifications = []
        notifications.append(
            {"message": f"Total {total_scans} butir telur telah dipindai oleh EggVision."}
        )
        if grade_counts_raw.get("C", 0) > 0:
            notifications.append(
                {
                    "message": f"Ada {grade_counts_raw['C']} butir Grade C, periksa kualitas sebelum dijual."
                }
            )

        # Status alat (dummy, tapi terstruktur)
        status_items = [
            {
                "label": "Konveyor Utama",
                "variant": "success",
                "is_on": True,
                "sub_items": [
                    {"label": "Motor Konveyor", "is_on": True},
                    {"label": "Sensor Proximity", "is_on": True},
                ],
            },
            {
                "label": "Vision Camera",
                "variant": "info",
                "is_on": True,
                "sub_items": [
                    {"label": "Kamera A1 (Kanan)", "is_on": True},
                    {"label": "Kamera A2 (Tengah)", "is_on": True},
                    {"label": "Kamera A3 (Kiri)", "is_on": True},
                ],
            },
            {
                "label": "Load Cell",
                "variant": "success",
                "is_on": True,
                "sub_items": [
                    {"label": "Load Cell 1", "is_on": True},
                    {"label": "Load Cell 2", "is_on": True},
                ],
            },
        ]

        # Tabel "Real Time Data" -> ambil 20 data terakhir
        cur.execute(
            """
            SELECT
                id,
                numeric_id,
                scanned_at,
                ketebalan,
                kebersihan,
                keutuhan,
                kesegaran,
                berat_telur
            FROM egg_scans
            WHERE user_id = %s
            ORDER BY scanned_at DESC
            LIMIT 20
            """,
            (user_id,),
        )
        scan_rows = cur.fetchall()

        records = []
        for idx, row in enumerate(scan_rows, start=1):
            records.append(
                {
                    "no": idx,
                    "idNumerik": row["numeric_id"] or f"EV-{row['id']}",
                    "tanggal": row["scanned_at"].strftime("%d/%m/%Y %H:%M")
                    if row["scanned_at"]
                    else "",
                    "ketebalan": row["ketebalan"] or "-",
                    "kebersihan": row["kebersihan"] or "-",
                    "keutuhan": row["keutuhan"] or "-",
                    "kesegaran": row["kesegaran"] or "-",
                    "beratTelur": f"{row['berat_telur']:.2f}"
                    if row["berat_telur"] is not None
                    else "-",
                }
            )

        table_meta = {
            "total_records": f"{total_scans} total data",
            "rows_shown": len(records),
        }

        header = _build_header(user_id, total_scans)

        cur.close()
        return {
            "header": header,
            "grades": grades,
            "grades_total": grades_total,
            "donut_r": donut_r,
            "notifications": notifications,
            "status_items": status_items,
            "table_meta": table_meta,
            "records": records,
            "active_menu": "dashboard",
        }

    finally:
        if conn:
            conn.close()
