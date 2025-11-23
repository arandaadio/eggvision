from utils.database import get_db_connection
import mysql.connector

def update_db():
    print("Menghubungkan ke database...")
    conn = get_db_connection()
    if not conn:
        return

    try:
        cur = conn.cursor()
        print("Menambahkan kolom 'tags' ke tabel 'news'...")
        # Menambahkan kolom tags bertipe TEXT agar bisa menampung banyak tag
        cur.execute("ALTER TABLE news ADD COLUMN tags TEXT NULL;")
        
        conn.commit()
        print("✅ Berhasil! Kolom tags telah ditambahkan.")
        
    except mysql.connector.Error as e:
        if e.errno == 1060:
            print("ℹ️ Kolom 'tags' sudah ada.")
        else:
            print(f"❌ Error: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    update_db()