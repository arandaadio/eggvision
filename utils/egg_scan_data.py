# from datetime import datetime, timedelta

# import random

# def get_dummy_egg_scans(user_id, n=20):
#     now = datetime.now()
#     # Buat 20 data terbaru ke belakang
#     scans = []
#     for i in range(n):
#         scans.append({
#             "numeric_id": 1000 + i,  # angka unik, bisa mulai dari angka berapa saja
#             "user_id": user_id,
#             "scanned_at": now - timedelta(minutes=3*i),            # data makin lama makin mundur
#             "ketebalan": round(random.uniform(0.30, 0.40), 2),     # misal tebal 0.30-0.40 mm
#             "kebersihan": round(random.uniform(80, 100), 1),       # skor 80-100
#             "keutuhan": random.choice(["utuh", "retak"]),          # atau integer jika di db
#             "kesegaran": round(random.uniform(7.5, 10), 2),        # contoh: skala 7.5-10
#             "berat_telur": round(random.uniform(50, 70), 1),       # berat, misal 50g-70g
#         })
#     return scans