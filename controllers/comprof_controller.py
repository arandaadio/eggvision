from flask import Blueprint, render_template, request, jsonify, session
from flask_login import current_user
import datetime
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

# --- CHAT ROUTES ---

@comprof_controller.route('/api/chat/send', methods=['POST'])
def comprof_send_chat():
    data = request.get_json()
    message = data.get('message')
    
    # Initialize variables
    user_id = None
    guest_name = None
    guest_email = None
    
    # Determine if user is logged in or guest
    if current_user.is_authenticated:
        user_id = current_user.id
        message_type = 'user_to_admin'
    else:
        guest_name = data.get('guest_name')
        guest_email = data.get('guest_email')
        message_type = 'guest_to_admin'
        
        if not guest_name or not guest_email:
            return jsonify({'success': False, 'error': 'Guest details required'})

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database error'})

    try:
        cur = conn.cursor()
        
        # FIX: Changed 'is_read' to 'status' and value FALSE to 'unread'
        query = """
            INSERT INTO chat_messages 
            (user_id, guest_name, guest_email, message, message_type, created_at, status) 
            VALUES (%s, %s, %s, %s, %s, NOW(), 'unread')
        """
        cur.execute(query, (user_id, guest_name, guest_email, message, message_type))
        conn.commit()
        cur.close()
        
        return jsonify({'success': True})
        
    except mysql.connector.Error as e:
        print(f"Error sending chat: {e}")
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@comprof_controller.route('/api/chat/history', methods=['GET'])
def comprof_get_chat_history():
    # Determine who we are fetching history for
    user_id = None
    guest_email = None
    
    if current_user.is_authenticated:
        user_id = current_user.id
    else:
        guest_email = request.args.get('guest_email')
        if not guest_email:
            return jsonify({'success': True, 'messages': []}) # No email, no history

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'})

    messages = []
    try:
        cur = conn.cursor(dictionary=True)
        
        if user_id:
            # Fetch for logged-in user
            query = """
                SELECT message, message_type, created_at 
                FROM chat_messages 
                WHERE user_id = %s 
                ORDER BY created_at ASC
            """
            cur.execute(query, (user_id,))
        else:
            # Fetch for guest by email
            query = """
                SELECT message, message_type, created_at 
                FROM chat_messages 
                WHERE guest_email = %s 
                ORDER BY created_at ASC
            """
            cur.execute(query, (guest_email,))
            
        messages = cur.fetchall()
        cur.close()
        
    except mysql.connector.Error as e:
        print(f"Error fetching chat history: {e}")
    finally:
        conn.close()

    return jsonify({'success': True, 'messages': messages})

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'})

    messages = []
    try:
        cur = conn.cursor(dictionary=True)
        
        if user_id:
            # Fetch for logged-in user
            query = """
                SELECT message, message_type, created_at 
                FROM chat_messages 
                WHERE user_id = %s 
                ORDER BY created_at ASC
            """
            cur.execute(query, (user_id,))
        else:
            # Fetch for guest by email
            query = """
                SELECT message, message_type, created_at 
                FROM chat_messages 
                WHERE guest_email = %s 
                ORDER BY created_at ASC
            """
            cur.execute(query, (guest_email,))
            
        messages = cur.fetchall()
        cur.close()
        
    except mysql.connector.Error as e:
        print(f"Error fetching chat history: {e}")
    finally:
        conn.close()

    return jsonify({'success': True, 'messages': messages})