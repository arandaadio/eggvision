from flask import Blueprint, render_template
from utils.database import get_db_connection
import mysql.connector

comprof_controller = Blueprint('comprof_controller', __name__)

@comprof_controller.route('/')
def comprof_beranda():
    """Homepage - accessible by everyone"""
    # Get published news from database for the homepage
    conn = get_db_connection()
    news_list = []
    
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM news WHERE is_published = TRUE ORDER BY published_at DESC LIMIT 10")
            news_list = cur.fetchall()
            cur.close()
        except mysql.connector.Error as e:
            print(f"Error fetching news: {e}")
        finally:
            if conn:
                conn.close()
    
    return render_template('comprof/beranda.html', news_list=news_list)

@comprof_controller.route('/berita')
def comprof_berita():
    """News page - accessible by everyone"""
    # Get published news from database
    conn = get_db_connection()
    news_list = []
    
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM news WHERE is_published = TRUE ORDER BY published_at DESC LIMIT 10")
            news_list = cur.fetchall()
            cur.close()
        except mysql.connector.Error as e:
            print(f"Error fetching news: {e}")
        finally:
            if conn:
                conn.close()
    
    return render_template('comprof/berita.html', news_list=news_list)

@comprof_controller.route('/layanan')
def comprof_layanan():
    """Services page - accessible by everyone"""
    return render_template('comprof/layanan.html')

@comprof_controller.route('/produk')
def comprof_produk():
    """Products page - accessible by everyone"""
    return render_template('comprof/produk.html')

@comprof_controller.route('/tentang-kami')
def comprof_tentang_kami():
    """About page - accessible by everyone"""
    return render_template('comprof/tentangkami.html')

@comprof_controller.route('/kontak')
def comprof_kontak():
    """Contact page - accessible by everyone"""
    return render_template('comprof/kontak.html')