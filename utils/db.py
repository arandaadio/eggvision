# utils/db.py
import mysql.connector
from mysql.connector import Error
from flask import current_app

from config import DB_CONFIG

def get_db_connection():
    """
    Helper untuk bikin koneksi MySQL.
    Konfigurasi diambil dari current_app.config:
      DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PORT (opsional)
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)

        if conn.is_connected():
            return conn

        return None
    except Error as e:
        print(f"[DB] MySQL connection error: {e}")
        return None
