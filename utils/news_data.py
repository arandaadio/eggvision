from datetime import datetime, timedelta

def get_dummy_news_data():
    """
    Mengembalikan list dictionary berisi 10 berita dummy.
    """
    now = datetime.now()

    news_data = [
        # --- 1. DARI EGGMIN ---
        {
            "title": "Selamat Datang di Era Baru Peternakan Digital bersama EggVision",
            "content": """Industri peternakan ayam petelur di Indonesia telah lama menghadapi tantangan dalam standarisasi kualitas. Proses penyortiran manual yang memakan waktu dan rentan kesalahan manusia seringkali menjadi penghambat efisiensi.
            Hari ini, kami dengan bangga memperkenalkan EggVision secara resmi kepada publik. EggVision bukan sekadar alat sortir, melainkan ekosistem digital yang menggabungkan kecerdasan buatan (AI) dan Internet of Things (IoT) untuk membantu peternak lokal naik kelas.
            Dengan teknologi Computer Vision, kami menjamin akurasi grading hingga 99%, mendeteksi retakan mikro yang tidak kasat mata, serta memastikan kebersihan kerabang telur sesuai standar SNI. Mari melangkah ke masa depan bersama EggVision.""",
            "image_url": "static/img/logoegg.png",
            "tags": "Dari EggMin",
            "published_at": now - timedelta(days=30)
        },

        # --- 2. EGG 101 ---
        {
            "title": "Apa itu Grading Telur? Panduan Lengkap untuk Pemula",
            "content": """Bagi masyarakat awam, telur mungkin terlihat sama saja. Namun, di dunia industri pangan, 'Grading Telur' adalah proses krusial yang menentukan harga dan kelayakan konsumsi.Grading adalah proses pengelompokan telur berdasarkan kualitas fisik (eksterior) dan isi (interior). Secara umum, telur dibagi menjadi:
            1. Grade AA/A: Cangkang bersih, bentuk oval sempurna, kuning telur di tengah, dan putih telur kental. Biasanya untuk pasar premium dan hotel.
            2. Grade B: Sedikit noda pada cangkang atau bentuk sedikit tidak beraturan. Cocok untuk industri roti (bakery).
            3. Grade C: Telur dengan kualitas terendah, biasanya langsung diproses menjadi telur cair atau tepung telur.
            EggVision mengotomatisasi proses ini menggunakan kamera canggih, menggantikan metode 'candling' manual yang melelahkan mata.""",
            "image_url": "https://www.peteandgerrys.com/cdn/shop/articles/Egg_Grades_Header.V3.png?v=1681313008&width=900",
            "tags": "Egg 101",
            "published_at": now - timedelta(days=25)
        },

        # --- 3. CERITA PENGGUNA ---
        {
            "title": "Transformasi Sinar Telur Abadi: Efisiensi Meningkat 40%",
            "content": """Fulan Setiawan, pendiri 'Sinar Telur Abadi', awalnya skeptis dengan digitalisasi. Peternakannya yang berlokasi di Blitar masih menggunakan metode sortir manual dengan tenaga kerja padat karya.
            "Kami sangat puas dengan kinerja awal dari mesin EggVision dan dukungan luar biasa dari tim customer supportnya," ujar Fulan saat kami wawancarai minggu lalu. 
            Sebelumnya, tingkat telur pecah (rejected) di peternakannya mencapai 5-8% karena penanganan manusia yang kurang hati-hati saat kelelahan. Setelah implementasi EggVision, angka tersebut turun drastis di bawah 1%. "Kami percaya bahwa ini akan menjadi investasi jangka panjang yang produktif bagi bisnis kami," tambahnya. Kini, Fulan bisa memantau hasil produksi harian langsung dari smartphone-nya.""",
            "image_url": "static/img/fulan.jpg",
            "tags": "Cerita Pengguna",
            "published_at": now - timedelta(days=18)
        },

        # --- 4. EGG 101 ---
        {
            "title": "Mengapa Harga Telur Fluktuatif? Ini Faktor Penyebabnya",
            "content": """Pernahkah Anda bertanya mengapa harga telur minggu ini bisa Rp26.000/kg, tapi minggu depan melonjak ke Rp32.000/kg? Fluktuasi harga telur dipengaruhi oleh mekanisme pasar yang kompleks.
            Faktor utama adalah Harga Pakan (Jagung & Konsentrat). Pakan menyumbang 70% dari biaya produksi. Jika harga jagung naik, harga telur pasti terkerek. Kedua adalah Cuaca dan Penyakit. Musim pancaroba sering menurunkan produktivitas ayam layer.
            Terakhir adalah Permintaan Musiman. Menjelang Lebaran atau Natal, permintaan bahan kue meningkat tajam. Memahami pola ini penting bagi peternak untuk mengatur strategi stok menggunakan fitur prediksi di EggMonitor.""",
            "image_url": "https://images.unsplash.com/photo-1693164309161-bdd92e6569c8?q=80&w=1470&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
            "tags": "Egg 101",
            "published_at": now - timedelta(days=14)
        },

        # --- 5. DARI EGGMIN ---
        {
            "title": "Update Sistem v2.0: Deteksi Kebersihan Cangkang Lebih Akurat",
            "content": """Kami mendengar masukan Anda! Banyak mitra peternak yang meminta fitur deteksi noda kotoran ayam yang lebih sensitif. Tim engineer EggVision telah bekerja keras selama dua bulan terakhir untuk melatih ulang model AI kami.
            Pada pembaruan v2.0 yang dirilis minggu ini, kami meningkatkan sensitivitas deteksi noda (feces/darah) pada cangkang telur. Algoritma baru ini mampu membedakan antara noda kotoran dan pigmen alami cangkang dengan akurasi lebih tinggi.
            Pembaruan ini otomatis terunduh ke perangkat EggVision yang terhubung ke internet. Pastikan perangkat Anda selalu online untuk mendapatkan performa terbaik.""",
            "image_url": "https://images.unsplash.com/photo-1755603784587-58f19674440f?q=80&w=1467&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
            "tags": "Dari EggMin",
            "published_at": now - timedelta(days=10)
        },

        # --- 6. CERITA PENGGUNA ---
        {
            "title": "Sari Sehat Katering: Kualitas Bahan Baku adalah Kunci",
            "content": """Dalam bisnis kuliner, konsistensi rasa dan kualitas bahan baku tidak bisa ditawar. Hal ini dipegang teguh oleh Rina Saraswati, pendiri 'Sari Sehat Katering' yang melayani ribuan porsi makanan sehat setiap harinya di Jakarta Selatan.
            "Saya selalu membeli telur di EggMart," ungkap Rina. Baginya, mencari supplier telur yang konsisten itu sulit. Kadang bagus, kadang banyak yang busuk atau cangkangnya tipis.
            "Proses pembeliannya sangat mudah dan kualitas telur yang kami terima selalu terjamin karena sistem gradingnya yang jelas," tambah Rina. Dengan membeli dari peternak yang terverifikasi EggVision, Rina tidak perlu lagi melakukan sortir ulang di dapurnya, menghemat waktu tim masaknya secara signifikan.""",
            "image_url": "static/img/fulana.jpg",
            "tags": "Cerita Pengguna",
            "published_at": now - timedelta(days=7)
        },

        # --- 7. EGG 101 ---
        {
            "title": "Evolusi Teknologi Grading: Dari Lilin hingga Artificial Intelligence",
            "content": """Jauh sebelum ada komputer, peternak mengecek kualitas telur menggunakan lilin di ruangan gelap untuk melihat isi telur. Metode ini disebut 'Candling'.
            Kemudian muncul mesin grading mekanik berdasarkan berat (weight grader). Ini membantu, tapi tidak bisa melihat retak atau kotoran. Di era modern, sensor akustik mulai digunakan untuk mendengar suara 'ting' yang berbeda pada telur retak.
            Kini, kita berada di era Computer Vision. Seperti yang dilakukan EggVision, kamera beresolusi tinggi mengambil gambar telur dari berbagai sisi, dan otak komputer (AI) menganalisanya dalam milidetik. Ini adalah inovasi tertinggi saat ini yang menggabungkan kecepatan dan ketelitian.""",
            "image_url": "https://advcloudfiles.advantech.com/cms/d1f8775c-575b-4941-9581-c971d5cefdf3/Content/GettyImages-820750246.jpg",
            "tags": "Egg 101",
            "published_at": now - timedelta(days=5)
        },

        # --- 8. CERITA PENGGUNA ---
        {
            "title": "Kisah Pak Budi: Peternak Kecil yang Berani Go Digital",
            "content": """Pak Budi (52) memiliki populasi ayam 3.000 ekor di pinggiran Bogor. Selama 15 tahun, ia menjual telurnya secara curah ke tengkulak dengan harga yang ditekan rendah karena alasan 'kualitas campur'.
            Tiga bulan lalu, Pak Budi mencoba menyewa mesin EggVision skala kecil. Hasilnya mengejutkan. Dengan memisahkan Grade A dan Grade B secara presisi, Pak Budi bisa menjual Grade A langsung ke supermarket lokal dengan harga 20% lebih tinggi dari harga tengkulak.
            "Dulu saya pasrah harga ditentukan orang. Sekarang saya punya data, saya tahu barang saya bagus, saya berani tawarkan harga pantas," kata Pak Budi dengan bangga. Digitalisasi bukan hanya milik perusahaan besar.""",
            "image_url": "https://images.pexels.com/photos/7782886/pexels-photo-7782886.jpeg",
            "tags": "Cerita Pengguna",
            "published_at": now - timedelta(days=3)
        },

        # --- 9. CERITA PENGGUNA ---
        {
            "title": "Menjaga Konsistensi Adonan Kue dengan Telur Grade A",
            "content": """Bagi Ibu Anita, pemilik 'Anita Bakery', kesegaran telur sangat mempengaruhi pengembangan adonan kue bolu. Telur yang encer (putih telur tidak kental) membuat kue bantat.
            Setelah beralih menggunakan telur dari supplier EggMart, komplain pelanggan tentang kue yang tidak mengembang berkurang drastis. "Sistem grading EggVision memastikan saya hanya dapat telur dengan Haugh Unit (kekentalan) yang tinggi. Itu rahasia kue saya tetap lembut," jelasnya.
            Fitur langganan di EggMart juga memudahkannya memastikan stok telur segar datang setiap pagi tanpa harus ke pasar.""",
            # Updated link to a direct image
            "image_url": "https://images.unsplash.com/photo-1653552900145-5679d740bbb6?q=80&w=687&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
            "tags": "Cerita Pengguna",
            "published_at": now - timedelta(days=1)
        },

        # --- 10. DARI EGGMIN ---
        {
            "title": "EggVision Meraih Penghargaan 'Best Agrotech Startup 2024'",
            "content": """Kami menutup tahun ini dengan kabar gembira! EggVision baru saja dinobatkan sebagai 'Best Agrotech Startup' dalam ajang Indonesia Digital Innovation Awards 2024.
            Penghargaan ini bukan hanya milik tim kami, tapi milik seluruh mitra peternak, pembeli, dan pengguna setia EggVision. Dedikasi Anda untuk memajukan ketahanan pangan Indonesia adalah motivasi terbesar kami.
            Komitmen kami tetap sama: menghadirkan teknologi yang membumi, terjangkau, dan berdampak nyata. Terima kasih telah mempercayai perjalanan ini bersama kami.""",
            "image_url": "https://images.unsplash.com/photo-1541329444622-e85b1a8980df?q=80&w=1470&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
            "tags": "Dari EggMin",
            "published_at": now
        }
    ]
    return news_data