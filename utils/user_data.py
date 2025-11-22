from flask_login import current_user

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
            "name": current_user.name if current_user.is_authenticated else "Pengguna",
            "tagline": "Giving up is an not option",
            "avatar_seed": current_user.name.lower().replace(" ", "") if current_user.is_authenticated else "user",
            "phone_display": "+62 813-1777-3184",
            "phone_raw": "+6281317773184",
        },
        "settings_items": settings_items,
    }