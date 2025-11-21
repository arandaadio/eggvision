import os
import numpy as np
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import load_img, img_to_array

# ====== MODEL & LABELS ======
# Sesuaikan path ini dengan path di server/dev-mu
model_keutuhan = load_model('/Users/reksasyahputra/Projects/eggvision-flask/static/model_keutuhan.keras')
model_color    = load_model('/Users/reksasyahputra/Projects/eggvision-flask/static/cangkang-cnn.keras')

# Label untuk masing-masing model
CLASS_NAMES_KEUTUHAN = ["Retak", "Utuh"]
CLASS_NAMES_COLOR    = ["Brown", "DarkBrown", "LightBrown"]  # urutan harus sama dengan training


def _preprocess_image(file_path):
    """Helper: load + preprocess image"""
    img = load_img(file_path, target_size=(224, 224))
    img_array = img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0) / 255.0
    return img_array


def predict_keutuhan_image(file_path):
    """Prediksi Retak / Utuh"""
    try:
        img_array = _preprocess_image(file_path)
        pred = model_keutuhan.predict(img_array)
        class_idx = np.argmax(pred)
        prediction_label = CLASS_NAMES_KEUTUHAN[class_idx]
        confidence = float(np.max(pred) * 100)
        return prediction_label, confidence
    except Exception as e:
        print(f"Prediction keutuhan error: {e}")
        return None, 0.0


def predict_color_image(file_path):
    """Prediksi Brown / DarkBrown / LightBrown"""
    try:
        img_array = _preprocess_image(file_path)
        pred = model_color.predict(img_array)
        class_idx = np.argmax(pred)
        prediction_label = CLASS_NAMES_COLOR[class_idx]
        confidence = float(np.max(pred) * 100)
        return prediction_label, confidence
    except Exception as e:
        print(f"Prediction color error: {e}")
        return None, 0.0


def _map_grade(color_label: str, keutuhan_label: str) -> str:
    """
    Kombinasi warna + keutuhan -> Grade A/B/C
    Aturan sesuai tabel:
      - LightBrown + Utuh   -> A
      - Brown + Utuh        -> B
      - DarkBrown + Utuh    -> C
      - LightBrown + Retak  -> B
      - Brown + Retak       -> C
      - DarkBrown + Retak   -> C
    """
    if color_label is None or keutuhan_label is None:
        return "C"  # fallback paling aman

    color_label = color_label.strip()
    keutuhan_label = keutuhan_label.strip()

    # Skor warna
    color_score_map = {
        "LightBrown": 2,
        "Brown": 1,
        "DarkBrown": 0
    }
    # Skor keutuhan
    intact_score_map = {
        "Utuh": 1,
        "Retak": 0
    }

    color_score = color_score_map.get(color_label, 0)
    intact_score = intact_score_map.get(keutuhan_label, 0)
    total_score = color_score + intact_score

    if total_score >= 3:
        return "A"
    elif total_score == 2:
        return "B"
    else:
        return "C"


def predict_image(file_path):
    """
    Prediksi gabungan:
    - model_keutuhan  -> Retak / Utuh
    - model_color     -> Brown / DarkBrown / LightBrown
    -> dikombinasikan menjadi Grade A/B/C

    Return:
      grade (str), grade_confidence (float), detail (dict)
    """
    try:
        # 1) Prediksi masing-masing model
        keutuhan_label, keutuhan_conf = predict_keutuhan_image(file_path)
        color_label, color_conf = predict_color_image(file_path)

        # 2) Kombinasikan ke Grade
        grade = _map_grade(color_label, keutuhan_label)

        # 3) Confidence gabungan (simple average)
        if keutuhan_conf == 0.0 and color_conf == 0.0:
            grade_conf = 0.0
        else:
            grade_conf = (keutuhan_conf + color_conf) / 2.0

        detail = {
            "keutuhan": keutuhan_label,
            "keutuhan_conf": keutuhan_conf,
            "color": color_label,
            "color_conf": color_conf,
        }

        return grade, grade_conf, detail

    except Exception as e:
        print(f"Prediction combined error: {e}")
        # fallback C
        detail = {
            "keutuhan": None,
            "keutuhan_conf": 0.0,
            "color": None,
            "color_conf": 0.0,
        }
        return "C", 0.0, detail
