import json
import numpy as np
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import load_img, img_to_array

# =============== LOAD MODEL & LABELS (sekali saja) ===============

IMG_SIZE = (224, 224)

# Sesuaikan path dengan punyamu
model_color     = load_model("static/model-ketebalan.keras")
model_keutuhan  = load_model("static/model-keutuhan.keras")
model_kebersih  = load_model("static/model-kebersihan.keras")

with open("static/model-ketebalan-class_names.json") as f:
    CLASS_NAMES_COLOR = json.load(f)          # ["Dark Brown","Brown","Light Brown"]

with open("static/model-keutuhan-class_names.json") as f:
    CLASS_NAMES_KEUTUHAN = json.load(f)      # ["Retak","Utuh"]

with open("static/model-kebersihan-class_names.json") as f:
    CLASS_NAMES_KEBERSIHAN = json.load(f)    # ["Noda","Bersih"]  (atau sebaliknya, sesuaikan)

# =============== PREPROCESS & PREDICT PER MODEL ===============

def _preprocess_image(file_path: str):
    img = load_img(file_path, target_size=IMG_SIZE)
    arr = img_to_array(img)          # TANPA /255.0 (EfficientNetB0 sudah preprocessing internal)
    arr = np.expand_dims(arr, axis=0)
    return arr

def predict_keutuhan_image(file_path: str):
    try:
        arr  = _preprocess_image(file_path)
        pred = model_keutuhan.predict(arr, verbose=0)[0]
        idx  = int(np.argmax(pred))
        label = CLASS_NAMES_KEUTUHAN[idx]
        conf  = float(np.max(pred) * 100)
        return label, conf
    except Exception as e:
        print(f"Prediction keutuhan error: {e}")
        return None, 0.0

def predict_color_image(file_path: str):
    try:
        arr  = _preprocess_image(file_path)
        pred = model_color.predict(arr, verbose=0)[0]
        idx  = int(np.argmax(pred))
        label = CLASS_NAMES_COLOR[idx]
        conf  = float(np.max(pred) * 100)
        return label, conf
    except Exception as e:
        print(f"Prediction color error: {e}")
        return None, 0.0

def predict_kebersihan_image(file_path: str):
    try:
        arr  = _preprocess_image(file_path)
        pred = model_kebersih.predict(arr, verbose=0)[0]
        idx  = int(np.argmax(pred))
        label = CLASS_NAMES_KEBERSIHAN[idx]
        conf  = float(np.max(pred) * 100)
        return label, conf
    except Exception as e:
        print(f"Prediction kebersihan error: {e}")
        return None, 0.0

# =============== PREDIKSI FITUR SAJA (untuk egg_scan) ===============

def predict_features(file_path: str):
    """
    Dipakai saat egg_scan / load model.
    Tidak butuh berat_kategori.
    Mengembalikan label + confidence dari 3 model.
    """
    keutuhan_label,   keutuhan_conf   = predict_keutuhan_image(file_path)
    color_label,      color_conf      = predict_color_image(file_path)
    kebersihan_label, kebersihan_conf = predict_kebersihan_image(file_path)

    return {
        "color": (color_label, color_conf),
        "keutuhan": (keutuhan_label, keutuhan_conf),
        "kebersihan": (kebersihan_label, kebersihan_conf),
    }

# =============== KESEGARAN (DITURUNKAN, TANPA MODEL) ===============

def _infer_kesegaran(
    color_label: str,
    keutuhan_label: str,
    kebersihan_label: str,
    berat_kategori: str,
) -> str:
    """
    Saat ini: tidak ada model kesegaran.
    Asumsi:
      - Semua telur yang diproses dianggap 'Segar' untuk keperluan grading.
      - Tabel menyebut Reject utk Utuh/Busuk & Retak/(Segar/Busuk),
        tapi karena kita tidak punya info Busuk, kita pakai 'Segar'.
    """
    return "Segar"

# =============== GRADING BERDASARKAN TABEL ===============

def _map_grade(
    color_label: str,
    keutuhan_label: str,
    berat_kategori: str,
    kebersihan_label: str,
    kesegaran_label: str,
) -> str:
    """
    Implementasi langsung dari tabel klasifikasi grading.
    """

    if (color_label is None or keutuhan_label is None or
        berat_kategori is None or kebersihan_label is None or
        kesegaran_label is None):
        return "Reject"

    color_label      = color_label.strip()
    keutuhan_label   = keutuhan_label.strip()
    berat_kategori   = berat_kategori.strip()
    kebersihan_label = kebersihan_label.strip()
    kesegaran_label  = kesegaran_label.strip()

    # ---------- RULE REJECT ----------
    # Reject: semua berat, semua ketebalan, semua kondisi jika:
    #   - Retak & Segar
    #   - Utuh & Busuk
    #   - Retak & Busuk
    if keutuhan_label == "Retak":
        return "Reject"
    if kesegaran_label == "Busuk":
        return "Reject"

    # Sampai sini: Utuh & Segar.

    # ---------- GRADE A ----------
    # Berat: Sedang/Besar; Warna: Dark Brown/Brown; Kebersihan: Bersih
    if berat_kategori in ["Sedang", "Besar"] \
       and color_label in ["Dark Brown", "Brown"] \
       and kebersihan_label == "Bersih":
        return "A"

    # ---------- GRADE B ----------
    # B1: Kecil, Tebal/Sedang, Bersih
    if berat_kategori == "Kecil" \
       and color_label in ["Dark Brown", "Brown"] \
       and kebersihan_label == "Bersih":
        return "B"

    # B2: Sedang/Besar, Tipis, Bersih
    if berat_kategori in ["Sedang", "Besar"] \
       and color_label == "Light Brown" \
       and kebersihan_label == "Bersih":
        return "B"

    # B3: Sedang/Besar, Tebal/Sedang, Noda
    if berat_kategori in ["Sedang", "Besar"] \
       and color_label in ["Dark Brown", "Brown"] \
       and kebersihan_label == "Noda":
        return "B"

    # ---------- GRADE C ----------
    # C1: Kecil, Tipis, Bersih
    if berat_kategori == "Kecil" \
       and color_label == "Light Brown" \
       and kebersihan_label == "Bersih":
        return "C"

    # C2: Kecil, Tebal/Sedang, Noda
    if berat_kategori == "Kecil" \
       and color_label in ["Dark Brown", "Brown"] \
       and kebersihan_label == "Noda":
        return "C"

    # C3: Sedang/Besar, Tipis, Noda
    if berat_kategori in ["Sedang", "Besar"] \
       and color_label == "Light Brown" \
       and kebersihan_label == "Noda":
        return "C"

    # Fallback konservatif
    return "C"

# =============== GRADING BERDASARKAN TABEL ===============

def _map_grade(
    color_label: str,
    keutuhan_label: str,
    berat_kategori: str,
    kebersihan_label: str,
    kesegaran_label: str,
) -> str:
    """
    Implementasi langsung dari tabel klasifikasi grading.
    """

    if (color_label is None or keutuhan_label is None or
        berat_kategori is None or kebersihan_label is None or
        kesegaran_label is None):
        return "Reject"

    color_label      = color_label.strip()
    keutuhan_label   = keutuhan_label.strip()
    berat_kategori   = berat_kategori.strip()
    kebersihan_label = kebersihan_label.strip()
    kesegaran_label  = kesegaran_label.strip()

    # ---------- RULE REJECT ----------
    # Reject: semua berat, semua ketebalan, semua kondisi jika:
    #   - Retak & Segar
    #   - Utuh & Busuk
    #   - Retak & Busuk
    if keutuhan_label == "Retak":
        return "Reject"
    if kesegaran_label == "Busuk":
        return "Reject"

    # Sampai sini: Utuh & Segar.

    # ---------- GRADE A ----------
    # Berat: Sedang/Besar; Warna: Dark Brown/Brown; Kebersihan: Bersih
    if berat_kategori in ["Sedang", "Besar"] \
       and color_label in ["Dark Brown", "Brown"] \
       and kebersihan_label == "Bersih":
        return "A"

    # ---------- GRADE B ----------
    # B1: Kecil, Tebal/Sedang, Bersih
    if berat_kategori == "Kecil" \
       and color_label in ["Dark Brown", "Brown"] \
       and kebersihan_label == "Bersih":
        return "B"

    # B2: Sedang/Besar, Tipis, Bersih
    if berat_kategori in ["Sedang", "Besar"] \
       and color_label == "Light Brown" \
       and kebersihan_label == "Bersih":
        return "B"

    # B3: Sedang/Besar, Tebal/Sedang, Noda
    if berat_kategori in ["Sedang", "Besar"] \
       and color_label in ["Dark Brown", "Brown"] \
       and kebersihan_label == "Noda":
        return "B"

    # ---------- GRADE C ----------
    # C1: Kecil, Tipis, Bersih
    if berat_kategori == "Kecil" \
       and color_label == "Light Brown" \
       and kebersihan_label == "Bersih":
        return "C"

    # C2: Kecil, Tebal/Sedang, Noda
    if berat_kategori == "Kecil" \
       and color_label in ["Dark Brown", "Brown"] \
       and kebersihan_label == "Noda":
        return "C"

    # C3: Sedang/Besar, Tipis, Noda
    if berat_kategori in ["Sedang", "Besar"] \
       and color_label == "Light Brown" \
       and kebersihan_label == "Noda":
        return "C"

    # Fallback konservatif
    return "C"

# =============== HITUNG GRADE (dipanggil setelah ada berat) ===============

def compute_grade(
    color_label: str,
    keutuhan_label: str,
    kebersihan_label: str,
    berat_kategori: str,
):
    """
    Hanya menghitung Grade berdasarkan tabel + kategori berat.
    Dipanggil SETELAH data load cell (atau dummy) tersedia.
    """
    kesegaran_label = _infer_kesegaran(
        color_label=color_label,
        keutuhan_label=keutuhan_label,
        kebersihan_label=kebersihan_label,
        berat_kategori=berat_kategori,
    )

    grade = _map_grade(
        color_label=color_label,
        keutuhan_label=keutuhan_label,
        berat_kategori=berat_kategori,
        kebersihan_label=kebersihan_label,
        kesegaran_label=kesegaran_label,
    )

    return grade, kesegaran_label

def predict_image(file_path: str, berat_kategori: str = None):
    feats = predict_features(file_path)
    color_label,      color_conf      = feats["color"]
    keutuhan_label,   keutuhan_conf   = feats["keutuhan"]
    kebersihan_label, kebersihan_conf = feats["kebersihan"]

    # Jika belum ada berat (dipanggil dari /upload sekarang), pakai default sementara
    if berat_kategori is None:
        berat_kategori = "Sedang"  # dummy; nanti diganti dari load cell

    grade, kesegaran_label = compute_grade(
        color_label=color_label,
        keutuhan_label=keutuhan_label,
        kebersihan_label=kebersihan_label,
        berat_kategori=berat_kategori,
    )

    confs = [color_conf, keutuhan_conf, kebersihan_conf]
    valid = [c for c in confs if c > 0.0]
    grade_conf = float(sum(valid) / len(valid)) if valid else 0.0

    detail = {
        "keutuhan": keutuhan_label,
        "keutuhan_conf": keutuhan_conf,
        "color": color_label,
        "color_conf": color_conf,
        "kebersihan": kebersihan_label,
        "kebersihan_conf": kebersihan_conf,
        "berat": berat_kategori,
        "kesegaran": kesegaran_label,
    }
    return grade, grade_conf, detail

# =============== PREDIKSI + GRADING SEKALIGUS (opsional) ===============

# def predict_image(file_path: str, berat_kategori: str):
#     """
#     Dipakai kalau kamu SUDAH punya berat_kategori saat memanggil.
#     Kalau belum, gunakan:
#       feats = predict_features(file_path)
#       grade, kesegaran = compute_grade(..., berat_kategori)
#     """
#     feats = predict_features(file_path)
#     color_label,      color_conf      = feats["color"]
#     keutuhan_label,   keutuhan_conf   = feats["keutuhan"]
#     kebersihan_label, kebersihan_conf = feats["kebersihan"]

#     grade, kesegaran_label = compute_grade(
#         color_label=color_label,
#         keutuhan_label=keutuhan_label,
#         kebersihan_label=kebersihan_label,
#         berat_kategori=berat_kategori,
#     )

#     confs = [color_conf, keutuhan_conf, kebersihan_conf]
#     valid = [c for c in confs if c > 0.0]
#     grade_conf = float(sum(valid) / len(valid)) if valid else 0.0

#     detail = {
#         "keutuhan": keutuhan_label,
#         "keutuhan_conf": keutuhan_conf,
#         "color": color_label,
#         "color_conf": color_conf,
#         "kebersihan": kebersihan_label,
#         "kebersihan_conf": kebersihan_conf,
#         "berat": berat_kategori,
#         "kesegaran": kesegaran_label,
#     }

#     return grade, grade_conf, detail
