# utils/report_data.py
from datetime import datetime
from utils.database import get_db_connection
from utils.dashboard_data import _build_header  # pakai helper yg sama


def build_report_data(user_id: int):
    """
    Data untuk halaman eggmonitor/laporan.html:
    - tabel histori (records)
    - ringkasan grade (grade_summary)
    - data grafik (hist_labels, hist_values)
    """
    conn = get_db_connection()
    if not conn:
        header = _build_header(user_id, 0)
        return {
            "header": header,
            "table_meta": {"total_records": "0 data", "rows_shown": 0},
            "records": [],
            "grade_summary": [],
            "hist_labels": [],
            "hist_values": [],
            "active_menu": "laporan",
        }

    try:
        cur = conn.cursor(dictionary=True)

        # Total data
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM egg_scans WHERE user_id = %s",
            (user_id,),
        )
        total_scans = cur.fetchone()["cnt"]

        # Records histori (ambil 200 terakhir)
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
                berat_telur,
                berat_cat,
                grade,
                kategori,
                parameter_minus,
                keterangan
            FROM egg_scans
            WHERE user_id = %s
            ORDER BY scanned_at DESC
            LIMIT 200
            """,
            (user_id,),
        )
        rows = cur.fetchall()

        records = []
        for idx, row in enumerate(rows, start=1):
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
                    "berat": f"{row['berat_telur']:.2f}",
                    "berat_cat": row["berat_cat"] or "-"
                    if row["berat_telur"] is not None
                    else "-",
                    "kategori": row["kategori"] or row["grade"],
                    "parameter": row["parameter_minus"] or "-",
                    "keterangan": row["keterangan"] or "-",
                }
            )

        table_meta = {
            "total_records": f"{total_scans} total data",
            "rows_shown": len(records),
        }

        # Ringkasan per grade untuk card di bawah grafik
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
        grade_counts_raw = {r["grade"]: r["cnt"] for r in grade_rows}
        total_for_pct = sum(grade_counts_raw.values()) or 1

        grade_summary = []
        for code in ["A", "B", "C"]:
            cnt = grade_counts_raw.get(code, 0)
            pct = round(cnt * 100 / total_for_pct) if total_for_pct else 0
            grade_summary.append(
                {
                    "label": f"Grade {code}",
                    "count": cnt,
                    "pct": pct,
                }
            )

        # Data untuk grafik: agregasi per tanggal scan
        cur.execute(
            """
            SELECT
                DATE(scanned_at) AS d,
                COUNT(*) AS cnt
            FROM egg_scans
            WHERE user_id = %s
            GROUP BY DATE(scanned_at)
            ORDER BY d ASC
            LIMIT 14
            """,
            (user_id,),
        )
        hist_rows = cur.fetchall()
        hist_labels = [
            row["d"].strftime("%d/%m") if isinstance(row["d"], datetime) else str(row["d"])
            for row in hist_rows
        ]
        hist_values = [int(row["cnt"]) for row in hist_rows]

        header = _build_header(user_id, total_scans)

        cur.close()
        return {
            "header": header,
            "table_meta": table_meta,
            "records": records,
            "grade_summary": grade_summary,
            "hist_labels": hist_labels,
            "hist_values": hist_values,
            "active_menu": "laporan",
        }

    finally:
        if conn:
            conn.close()
