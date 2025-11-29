import mysql.connector
from config import DB_CONFIG

def fix_database():
    """Fix the orders table status ENUM values"""
    conn = mysql.connector.connect(**DB_CONFIG)
    if not conn:
        print("❌ Failed to connect to database")
        return

    try:
        cur = conn.cursor(dictionary=True)

        print("🔍 Checking current orders status values...")
        cur.execute("SELECT DISTINCT status FROM orders")
        current_statuses = cur.fetchall()
        print("Current status values in orders table:", [s['status'] for s in current_statuses])

        # Step 1: Modify the orders table to include all Midtrans status values
        print("🔄 Updating orders table structure...")
        cur.execute('''
            ALTER TABLE orders 
            MODIFY COLUMN status ENUM(
                'pending', 'paid', 'settlement', 'capture', 'cancelled', 'expired', 'refunded', 'expire'
            ) DEFAULT 'pending'
        ''')

        # Step 2: Update any 'expire' values to 'expired' for consistency
        print("🔄 Updating 'expire' status to 'expired'...")
        cur.execute("UPDATE orders SET status = 'expired' WHERE status = 'expire'")

        # Step 3: Final check
        cur.execute("SELECT DISTINCT status FROM orders")
        final_statuses = cur.fetchall()
        print("✅ Final status values in orders table:", [s['status'] for s in final_statuses])

        conn.commit()
        print("✅ Database fixed successfully!")

    except mysql.connector.Error as e:
        print(f"❌ Database fix failed: {e}")
        conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    fix_database()