import json
import numpy as np
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import load_img, img_to_array

# ====== MODEL & LABELS ======
# Sesuaikan path ini dengan path di server/dev-mu
model_color    = load_model("static/model-ketebalan.keras")
model_keutuhan = load_model("static/model-keutuhan.keras")

with open("static/model-ketebalan-class_names.json") as f:
    CLASS_NAMES_COLOR = json.load(f)          # contoh: ["Dark Brown","Brown","Light Brown"]

with open("static/model-keutuhan-class_names.json") as f:
    CLASS_NAMES_KEUTUHAN = json.load(f)      # ["Retak","Utuh"]

IMG_SIZE = (224, 224)

# ====== PREPROCESS & PREDICT TIAP MODEL ======
def _preprocess_image(file_path):
    img = load_img(file_path, target_size=IMG_SIZE)
    arr = img_to_array(img)          # TANPA /255.0 (EfficientNetB0 sudah punya preprocessing)
    arr = np.expand_dims(arr, axis=0)
    return arr

def predict_keutuhan_image(file_path):
    try:
        arr = _preprocess_image(file_path)
        pred = model_keutuhan.predict(arr, verbose=0)[0]
        idx  = int(np.argmax(pred))
        label = CLASS_NAMES_KEUTUHAN[idx]
        conf  = float(np.max(pred) * 100)
        return label, conf
    except Exception as e:
        print(f"Prediction keutuhan error: {e}")
        return None, 0.0

def predict_color_image(file_path):
    try:
        arr = _preprocess_image(file_path)
        pred = model_color.predict(arr, verbose=0)[0]
        idx  = int(np.argmax(pred))
        label = CLASS_NAMES_COLOR[idx]
        conf  = float(np.max(pred) * 100)
        return label, conf
    except Exception as e:
        print(f"Prediction color error: {e}")
        return None, 0.0

# ====== GRADING ======
def _map_grade(
    color_label: str,
    keutuhan_label: str,
    berat_kategori: str = None,
    kebersihan_label: str = None,
    kesegaran_label: str = None,
) -> str:
    # fallback jika prediksi gagal
    if color_label is None or keutuhan_label is None:
        return "Reject"

    color_label    = color_label.strip()
    keutuhan_label = keutuhan_label.strip()

    # 1. RULE REJECT SEDERHANA (saat ini)
    if keutuhan_label == "Retak":
        return "Reject"

    # 2. SAAT BERAT / KEBERSIHAN / KESEGARAN BELUM DIGUNAKAN:
    if berat_kategori is None and kebersihan_label is None and kesegaran_label is None:
        # grading sederhana berdasar warna + Utuh
        if color_label == "Dark Brown":
            return "A"   # Tebal
        elif color_label == "Brown":
            return "B"   # Sedang
        elif color_label == "Light Brown":
            return "C"   # Tipis
        else:
            return "C"

    # 3. NANTI JIKA PARAMETER LAIN SUDAH ADA, TAMBAH IF–ELSE DI SINI
    # contoh pola:
    # if kesegaran_label == "Busuk": return "Reject"
    # dst mengikuti tabelmu

    # fallback akhir
    return "C"

# ====== PREDIKSI GABUNGAN ======
def predict_image(
    file_path: str,
    berat_kategori: str = None,
    kebersihan_label: str = None,
    kesegaran_label: str = None,
):
    """
    Prediksi gabungan:
    - model_keutuhan  -> Retak / Utuh
    - model_color     -> Dark Brown / Brown / Light Brown
    + (opsional) berat, kebersihan, kesegaran
    -> Grade A/B/C/Reject
    """
    try:
        keutuhan_label, keutuhan_conf = predict_keutuhan_image(file_path)
        color_label,    color_conf    = predict_color_image(file_path)

        grade = _map_grade(
            color_label=color_label,
            keutuhan_label=keutuhan_label,
            berat_kategori=berat_kategori,
            kebersihan_label=kebersihan_label,
            kesegaran_label=kesegaran_label,
        )

        if keutuhan_conf == 0.0 and color_conf == 0.0:
            grade_conf = 0.0
        else:
            grade_conf = (keutuhan_conf + color_conf) / 2.0

        detail = {
            "keutuhan": keutuhan_label,
            "keutuhan_conf": keutuhan_conf,
            "color": color_label,
            "color_conf": color_conf,
            "berat": berat_kategori,
            "kebersihan": kebersihan_label,
            "kesegaran": kesegaran_label,
        }

        return grade, grade_conf, detail

    except Exception as e:
        print(f"Prediction combined error: {e}")
        detail = {
            "keutuhan": None,
            "keutuhan_conf": 0.0,
            "color": None,
            "color_conf": 0.0,
            "berat": berat_kategori,
            "kebersihan": kebersihan_label,
            "kesegaran": kesegaran_label,
        }
        return "Reject", 0.0, detail


# def _map_grade(
#     color_label: str,
#     keutuhan_label: str,
#     berat_kategori: str,
#     kebersihan_label: str,
#     kesegaran_label: str,
# ) -> str:
#     """
#     Menentukan Grade A/B/C/Reject berdasarkan tabel:

#     - color_label      : "Dark Brown", "Brown", "Light Brown"
#     - keutuhan_label   : "Retak", "Utuh"
#     - berat_kategori   : "Kecil", "Sedang", "Besar"
#     - kebersihan_label : "Tidak Bernoda", "Bernoda"
#     - kesegaran_label  : "Segar", "Busuk"
#     """

#     if (color_label is None or keutuhan_label is None or
#         berat_kategori is None or kebersihan_label is None or
#         kesegaran_label is None):
#         return "Reject"  # fallback aman

#     color_label      = color_label.strip()
#     keutuhan_label   = keutuhan_label.strip()
#     berat_kategori   = berat_kategori.strip()
#     kebersihan_label = kebersihan_label.strip()
#     kesegaran_label  = kesegaran_label.strip()

#     # 1. Rule Reject (paling keras)
#     # Reject: semua berat, semua ketebalan, semua kebersihan, jika:
#     #   - Retak & Segar
#     #   - Utuh & Busuk
#     #   - Retak & Busuk
#     if kesegaran_label == "Busuk":
#         return "Reject"
#     if keutuhan_label == "Retak":
#         return "Reject"

#     # Pada titik ini: keutuhan = Utuh dan kesegaran = Segar

#     # 2. Grade A
#     if berat_kategori in ["Sedang", "Besar"] \
#        and color_label in ["Dark Brown", "Brown"] \
#        and kebersihan_label == "Tidak Bernoda":
#         return "A"

#     # 3. Grade B
#     # B1: <50g (Kecil), Tebal/Sedang, Tidak Bernoda, Utuh, Segar
#     if berat_kategori == "Kecil" \
#        and color_label in ["Dark Brown", "Brown"] \
#        and kebersihan_label == "Tidak Bernoda":
#         return "B"

#     # B2: Besar/Sedang, Tipis, Tidak Bernoda, Utuh, Segar
#     if berat_kategori in ["Sedang", "Besar"] \
#        and color_label == "Light Brown" \
#        and kebersihan_label == "Tidak Bernoda":
#         return "B"

#     # B3: Besar/Sedang, Tebal/Sedang, Bernoda, Utuh, Segar
#     if berat_kategori in ["Sedang", "Besar"] \
#        and color_label in ["Dark Brown", "Brown"] \
#        and kebersihan_label == "Bernoda":
#         return "B"

#     # 4. Grade C
#     # C1: <50g (Kecil), Tipis, Tidak Bernoda, Utuh, Segar
#     if berat_kategori == "Kecil" \
#        and color_label == "Light Brown" \
#        and kebersihan_label == "Tidak Bernoda":
#         return "C"

#     # C2: <50g (Kecil), Tebal/Sedang, Bernoda, Utuh, Segar
#     if berat_kategori == "Kecil" \
#        and color_label in ["Dark Brown", "Brown"] \
#        and kebersihan_label == "Bernoda":
#         return "C"

#     # C3: Sedang/Besar, Tipis, Bernoda, Utuh, Segar
#     if berat_kategori in ["Sedang", "Besar"] \
#        and color_label == "Light Brown" \
#        and kebersihan_label == "Bernoda":
#         return "C"

#     # 5. Fallback
#     # Kalau ada kombinasi lain yang tidak tercakup tabel, kamu bisa pilih:
#     return "C"  # atau "Reject" jika ingin lebih ketat


# def predict_image(file_path, berat_kategori, kebersihan_label, kesegaran_label):
#     """
#     Prediksi gabungan:
#     - model_keutuhan  -> Retak / Utuh
#     - model_color     -> Dark Brown / Brown / Light Brown
#     + input tambahan: berat, kebersihan, kesegaran
#     -> Grade A/B/C/Reject
#     """
#     try:
#         keutuhan_label, keutuhan_conf = predict_keutuhan_image(file_path)
#         color_label, color_conf = predict_color_image(file_path)

#         grade = _map_grade(
#             color_label=color_label,
#             keutuhan_label=keutuhan_label,
#             berat_kategori=berat_kategori,
#             kebersihan_label=kebersihan_label,
#             kesegaran_label=kesegaran_label,
#         )

#         if keutuhan_conf == 0.0 and color_conf == 0.0:
#             grade_conf = 0.0
#         else:
#             grade_conf = (keutuhan_conf + color_conf) / 2.0

#         detail = {
#             "keutuhan": keutuhan_label,
#             "keutuhan_conf": keutuhan_conf,
#             "color": color_label,
#             "color_conf": color_conf,
#             "berat": berat_kategori,
#             "kebersihan": kebersihan_label,
#             "kesegaran": kesegaran_label,
#         }

#         return grade, grade_conf, detail

#     except Exception as e:
#         print(f"Prediction combined error: {e}")
#         detail = {
#             "keutuhan": None,
#             "keutuhan_conf": 0.0,
#             "color": None,
#             "color_conf": 0.0,
#             "berat": berat_kategori,
#             "kebersihan": kebersihan_label,
#             "kesegaran": kesegaran_label,
#         }
#         return "Reject", 0.0, detail

