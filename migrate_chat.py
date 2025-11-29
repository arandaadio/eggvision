import mysql.connector
import os
from mysql.connector import Error

# ==========================================
# CONFIGURATION
# Update these with your specific database details
# ==========================================
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',      # Replace with your DB username
    'password': '',      # Replace with your DB password
    'database': 'eggvision' # Replace with your DB name
}

def migrate_database():
    conn = None
    try:
        print("🔌 Connecting to database...")
        conn = mysql.connector.connect(**DB_CONFIG)
        if conn.is_connected():
            print("✅ Connected.")
            cur = conn.cursor()

            # ---------------------------------------------------------
            # 1. Update chat_sessions table
            # ---------------------------------------------------------
            print("\n[1/3] Updating 'chat_sessions' table structure...")
            try:
                # Check if column already exists to prevent errors on re-run
                cur.execute("""
                    SELECT count(*) 
                    FROM information_schema.COLUMNS 
                    WHERE (TABLE_SCHEMA = %s) 
                      AND (TABLE_NAME = 'chat_sessions') 
                      AND (COLUMN_NAME = 'seller_id')
                """, (DB_CONFIG['database'],))
                
                if cur.fetchone()[0] == 0:
                    query_sessions = """
                        ALTER TABLE chat_sessions
                        ADD COLUMN seller_id INT NULL AFTER user_id,
                        ADD CONSTRAINT fk_session_seller 
                        FOREIGN KEY (seller_id) REFERENCES users(id) ON DELETE SET NULL;
                    """
                    cur.execute(query_sessions)
                    print("   -> 'seller_id' column added successfully.")
                else:
                    print("   -> 'seller_id' column already exists. Skipping.")
            except Error as e:
                print(f"   ❌ Error updating chat_sessions: {e}")

            # ---------------------------------------------------------
            # 2. Data Cleanup (Optional but Recommended)
            # ---------------------------------------------------------
            # Since we are changing the ENUM list and REMOVING 'user_to_admin'/'admin_to_user',
            # existing rows with those values might cause errors or become empty strings ('').
            # We map them to the closest new valid values before altering.
            print("\n[2/3] Migrating legacy message types (Data Cleanup)...")
            try:
                # Update 'user_to_admin' -> 'guest_to_admin' (or 'pengusaha_to_admin' if you prefer)
                cur.execute("UPDATE chat_messages SET message_type = 'guest_to_admin' WHERE message_type = 'user_to_admin'")
                
                # Update 'admin_to_user' -> 'admin_to_guest'
                cur.execute("UPDATE chat_messages SET message_type = 'admin_to_guest' WHERE message_type = 'admin_to_user'")
                
                conn.commit()
                print("   -> Legacy data mapped to new types successfully.")
            except Error as e:
                print(f"   ⚠️  Warning during data cleanup (might fail if columns strictly don't match): {e}")

            # ---------------------------------------------------------
            # 3. Update chat_messages table
            # ---------------------------------------------------------
            print("\n[3/3] Updating 'chat_messages' ENUM columns...")
            try:
                query_messages = """
                    ALTER TABLE chat_messages
                    MODIFY COLUMN message_type ENUM(
                        'guest_to_admin',
                        'admin_to_guest',       
                        'pembeli_to_pengusaha',
                        'pengusaha_to_pembeli',
                        'pengusaha_to_admin',
                        'admin_to_pengusaha'
                    ) NOT NULL;
                """
                cur.execute(query_messages)
                print("   -> 'message_type' ENUM updated successfully.")
            except Error as e:
                print(f"   ❌ Error updating chat_messages: {e}")

            # Commit all changes
            conn.commit()
            print("\n✨ Database migration completed successfully!")

    except Error as e:
        print(f"\n❌ Fatal Database Error: {e}")
    finally:
        if conn and conn.is_connected():
            conn.close()
            print("🔌 Connection closed.")

if __name__ == "__main__":
    migrate_database()