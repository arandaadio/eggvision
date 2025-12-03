import json
import numpy as np
import random
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import load_img, img_to_array

# =============== LOAD MODEL & LABELS (sekali saja) ===============

IMG_SIZE = (224, 224)

try:
    # Sesuaikan path dengan punyamu
    model_color      = load_model("static/model-ketebalan.keras")
    model_keutuhan   = load_model("static/model-keutuhan.keras")
    model_kebersih   = load_model("static/model-kebersihan.keras")

    with open("static/model-ketebalan-class_names.json") as f:
        CLASS_NAMES_COLOR = json.load(f)          # ["Dark Brown","Brown","Light Brown"]

    with open("static/model-keutuhan-class_names.json") as f:
        CLASS_NAMES_KEUTUHAN = json.load(f)       # ["Retak","Utuh"]

    with open("static/model-kebersihan-class_names.json") as f:
        CLASS_NAMES_KEBERSIHAN = json.load(f)     # ["Noda","Bersih"]

except Exception as e:
    print(f"Error loading models: {e}")
    # Dummy classes for fallback if models fail to load
    CLASS_NAMES_COLOR = ["Brown"]
    CLASS_NAMES_KEUTUHAN = ["Utuh"]
    CLASS_NAMES_KEBERSIHAN = ["Bersih"]


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
        return "Utuh", 0.0 # Fallback

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
        return "Brown", 0.0 # Fallback

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
        return "Bersih", 0.0 # Fallback

# =============== PREDIKSI FITUR SAJA (untuk egg_scan) ===============

def predict_features(file_path: str):
    """
    Dipakai saat egg_scan / load model.
    Mengembalikan label + confidence dari 3 model.
    """
    keutuhan_label,   keutuhan_conf    = predict_keutuhan_image(file_path)
    color_label,      color_conf       = predict_color_image(file_path)
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

    color_label       = color_label.strip()
    keutuhan_label    = keutuhan_label.strip()
    berat_kategori    = berat_kategori.strip()
    kebersihan_label = kebersihan_label.strip()
    kesegaran_label  = kesegaran_label.strip()

    # ---------- RULE REJECT ----------
    if keutuhan_label == "Retak":
        return "Reject"
    if kesegaran_label == "Busuk":
        return "Reject"

    # Sampai sini: Utuh & Segar.

    # ---------- GRADE A ----------
    if berat_kategori in ["Sedang", "Besar"] \
       and color_label in ["Dark Brown", "Brown"] \
       and kebersihan_label == "Bersih":
        return "A"

    # ---------- GRADE B ----------
    # B1
    if berat_kategori == "Kecil" \
       and color_label in ["Dark Brown", "Brown"] \
       and kebersihan_label == "Bersih":
        return "B"

    # B2
    if berat_kategori in ["Sedang", "Besar"] \
       and color_label == "Light Brown" \
       and kebersihan_label == "Bersih":
        return "B"

    # B3
    if berat_kategori in ["Sedang", "Besar"] \
       and color_label in ["Dark Brown", "Brown"] \
       and kebersihan_label == "Noda":
        return "B"

    # ---------- GRADE C ----------
    # C1
    if berat_kategori == "Kecil" \
       and color_label == "Light Brown" \
       and kebersihan_label == "Bersih":
        return "C"

    # C2
    if berat_kategori == "Kecil" \
       and color_label in ["Dark Brown", "Brown"] \
       and kebersihan_label == "Noda":
        return "C"

    # C3
    if berat_kategori in ["Sedang", "Besar"] \
       and color_label == "Light Brown" \
       and kebersihan_label == "Noda":
        return "C"
    
    # Edge cases for Small & Light Brown & Noda -> C
    if berat_kategori == "Kecil" and color_label == "Light Brown" and kebersihan_label == "Noda":
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
    color_label,      color_conf       = feats["color"]
    keutuhan_label,   keutuhan_conf    = feats["keutuhan"]
    kebersihan_label, kebersihan_conf = feats["kebersihan"]
    
    # --- SIMULASI BERAT RANDOM JIKA TIDAK ADA INPUT ---
    # Berat Telur Ayam Ras (Standar SNI):
    # Kecil: < 50g
    # Sedang: 50g - 60g
    # Besar: > 60g
    
    simulated_weight_g = 0.0

    if berat_kategori is None:
        # Random choice weighted towards "Sedang" as it is most common
        choices = ["Kecil", "Sedang", "Besar"]
        weights = [0.2, 0.6, 0.2] # 20% Kecil, 60% Sedang, 20% Besar
        berat_kategori = random.choices(choices, weights=weights, k=1)[0]
        
        # Generate random gram based on category
        if berat_kategori == "Kecil":
            simulated_weight_g = round(random.uniform(40.0, 49.9), 2)
        elif berat_kategori == "Sedang":
            simulated_weight_g = round(random.uniform(50.0, 59.9), 2)
        else: # Besar
            simulated_weight_g = round(random.uniform(60.0, 75.0), 2)

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
        "berat": berat_kategori, # Kategori Text (Kecil/Sedang/Besar)
        "berat_telur": simulated_weight_g, # Numeric value
        "kesegaran": kesegaran_label,
    }
    return grade, grade_conf, detail