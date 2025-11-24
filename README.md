<p align="center">
  <img src="static/img/logoegg.png" alt="EggVision Logo" width="120" height="120">
</p>

# 🥚 EggVision

**Platform all-in-one untuk marketplace dan grading telur ayam konsumsi otomatis bagi peternak ayam Indonesia**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0-green?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.0-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

[Demo] • [Dokumentasi] • [Kontribusi]

---

## 📖 Tentang EggVision

**EggVision** hadir sebagai solusi revolusioner untuk mendigitalisasi industri peternakan ayam petelur di Indonesia. Kami menggabungkan kecerdasan buatan (Computer Vision) dengan platform e-commerce untuk memotong rantai distribusi yang panjang dan memastikan standarisasi kualitas telur.

Sistem kami membantu peternak melakukan **grading otomatis** (sortir kualitas) dan langsung menghubungkan mereka dengan pembeli melalui **EggMart**, serta memantau performa bisnis melalui dashboard **EggMonitor**.

## 🚀 Fitur Utama

### 🤖 EggVision Machine (AI Grading)
Sistem grading otomatis menggunakan *Computer Vision* untuk mendeteksi kualitas telur berdasarkan:
* **Kebersihan Cangkang:** Mendeteksi noda kotoran atau darah.
* **Keutuhan:** Mendeteksi keretakan mikro (crack detection).
* **Ukuran/Berat:** Klasifikasi Grade A, B, atau C secara presisi.

### 🛒 EggMart (Marketplace)
Platform jual beli khusus telur yang terintegrasi langsung dengan hasil grading.
* Pembeli mendapatkan jaminan kualitas sesuai Grade.
* Peternak mendapatkan harga yang lebih adil.
* Integrasi pembayaran digital (Midtrans).

### 📊 EggMonitor (Dashboard Pengusaha)
Pusat komando bagi pemilik peternakan.
* **Real-time Analytics:** Memantau jumlah produksi harian.
* **Inventory Management:** Stok telur otomatis terupdate dari hasil scan mesin.
* **Financial Report:** Laporan penjualan otomatis.

### 🛡️ EggMin (Admin Panel)
Panel administrasi pusat untuk mengelola user, berita edukasi (Egg 101), dan moderasi transaksi serta chat support.

---

## 🛠️ Teknologi yang Digunakan

| Kategori | Teknologi |
| :--- | :--- |
| **Backend** | Python, Flask (Blueprints Architecture) |
| **Frontend** | HTML5, Tailwind CSS, Alpine.js |
| **Database** | MySQL |
| **AI/ML** | TensorFlow / OpenCV (Image Processing) |
| **Payment** | Midtrans API |
| **Auth** | Flask-Login |

---

## 📂 Struktur Project

```text
eggvision-flask/
├── controllers/       # Logika backend (Auth, EggMart, EggMonitor, EggMin)
├── models/            # Model database user dan transaksi
├── static/            # Aset CSS, JS, Image Uploads
│   ├── css/           # Tailwind input & output
│   ├── img/           # Logo dan aset gambar
│   └── uploads/       # Gambar berita & hasil scan telur
├── templates/         # File HTML (Jinja2)
│   ├── auth/          # Login & Register
│   ├── comprof/       # Company Profile (Landing Page)
│   ├── eggmart/       # Halaman Marketplace
│   ├── eggmin/        # Halaman Admin
│   └── eggmonitor/    # Dashboard Peternak
├── utils/             # Helper functions (Database, ML Prediction)
├── app.py             # Entry point aplikasi
└── requirements.txt   # Daftar dependensi

-----

## Cara Menjalankan (Localhost)

Ikuti langkah berikut untuk menjalankan EggVision di komputer lokal:

1.  **Clone Repository**

    ```bash
    git clone [https://github.com/username/EggVision.git](https://github.com/username/EggVision.git)
    cd EggVision
    ```

2.  **Buat Virtual Environment**

    ```bash
    python -m venv .venv
    # Windows
    .venv\Scripts\activate
    # Mac/Linux
    source .venv/bin/activate
    ```

3.  **Install Dependensi**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Konfigurasi Environment (.env)**
    Buat file `.env` dan sesuaikan dengan konfigurasi database MySQL:

    ```env
    DB_HOST=localhost
    DB_USER=root
    DB_PASSWORD=
    DB_NAME=eggvision
    SECRET_KEY=your_db_key
    MAIL_USERNAME=your_mail_name
    MAIL_PASSWORD=your_mail_pass
    MIDTRANS_MERCHAT_ID=your_merchant_id
    MIDTRANS_CLIENT_KEY=your_client_key
    MIDTRANS_SERVER_KEY=your_server_key
    MIDTRANS_IS_PRODUCTION=false
    ```

5.  **Jalankan Aplikasi**

    ```bash
    python app.py
    ```

    Buka browser dan akses `http://localhost:5001`

-----


Dibuat dengan ❤️ oleh 🥚 Tim EggVision (TDCFives)\</p\>
2025 EggVision. Hak Cipta Dilindungi.


```
```