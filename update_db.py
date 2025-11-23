from utils.database import get_db_connection
import mysql.connector

def add_columns():
    print("Sedang menghubungkan ke database...")
    conn = get_db_connection()
    
    if conn is None:
        print("Gagal terhubung ke database!")
        return

    try:
        cur = conn.cursor()
        
        print("Menambahkan fitur Pin dan Archive...")
        
        # 1. Tambah kolom is_pinned
        try:
            cur.execute("ALTER TABLE chat_sessions ADD COLUMN is_pinned BOOLEAN DEFAULT FALSE;")
            print("✅ Berhasil menambahkan kolom 'is_pinned'.")
        except mysql.connector.Error as err:
            if err.errno == 1060: # Error jika kolom sudah ada
                print("ℹ️ Kolom 'is_pinned' sudah ada.")
            else:
                print(f"⚠️ Warning: {err}")

        # 2. Tambah kolom is_archived
        try:
            cur.execute("ALTER TABLE chat_sessions ADD COLUMN is_archived BOOLEAN DEFAULT FALSE;")
            print("✅ Berhasil menambahkan kolom 'is_archived'.")
        except mysql.connector.Error as err:
            if err.errno == 1060: 
                print("ℹ️ Kolom 'is_archived' sudah ada.")
            else:
                print(f"⚠️ Warning: {err}")

        conn.commit()
        print("\nSelesai! Database siap untuk fitur baru.")
        
    except mysql.connector.Error as e:
        print(f"Terjadi Kesalahan Database: {e}")
        
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    add_columns()