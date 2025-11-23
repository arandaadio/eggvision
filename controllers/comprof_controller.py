from flask import Blueprint, render_template, request, jsonify, session
from flask_login import current_user
import datetime
from datetime import timedelta
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
        finally:
            conn.close()
    return render_template('comprof/beranda.html', news_list=news_list)

@comprof_controller.route('/berita')
def comprof_berita():
    """News page with Search, Tag Filter, and Date Sort"""
    conn = get_db_connection()
    news_list = []
    unique_tags = set()
    
    # Get Filter Parameters
    search_query = request.args.get('q', '').strip()
    tag_filter = request.args.get('tag', '').strip()
    time_filter = request.args.get('time', 'all') # recent, yesterday, week, month

    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            
            # 1. Base Query
            sql = "SELECT * FROM news WHERE is_published = TRUE"
            params = []

            # 2. Apply Search
            if search_query:
                sql += " AND (title LIKE %s OR content LIKE %s)"
                params.extend([f"%{search_query}%", f"%{search_query}%"])

            # 3. Apply Tag Filter
            if tag_filter:
                # Simple LIKE check for comma separated tags
                sql += " AND tags LIKE %s"
                params.append(f"%{tag_filter}%")

            # 4. Apply Time Filter
            now = datetime.datetime.now()
            if time_filter == 'yesterday':
                yesterday = now - timedelta(days=1)
                sql += " AND published_at >= %s"
                params.append(yesterday.strftime('%Y-%m-%d 00:00:00'))
            elif time_filter == 'week':
                week_ago = now - timedelta(days=7)
                sql += " AND published_at >= %s"
                params.append(week_ago.strftime('%Y-%m-%d 00:00:00'))
            elif time_filter == 'month':
                month_ago = now - timedelta(days=30)
                sql += " AND published_at >= %s"
                params.append(month_ago.strftime('%Y-%m-%d 00:00:00'))

            # 5. Order By
            sql += " ORDER BY published_at DESC"

            cur.execute(sql, tuple(params))
            news_list = cur.fetchall()

            # 6. Fetch All Tags for the Navbar
            # We fetch all published news to collect unique tags
            cur.execute("SELECT tags FROM news WHERE is_published = TRUE")
            all_tags_rows = cur.fetchall()
            for row in all_tags_rows:
                if row['tags']:
                    # Split comma separated string and clean whitespace
                    tags = [t.strip() for t in row['tags'].split(',')]
                    unique_tags.update(tags)
            
            cur.close()
        except mysql.connector.Error as e:
            print(f"Error fetching news: {e}")
        finally:
            conn.close()
    
    return render_template('comprof/berita.html', 
                           news_list=news_list, 
                           tags=sorted(list(unique_tags)),
                           active_filters={
                               'q': search_query,
                               'tag': tag_filter,
                               'time': time_filter
                           })

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

# --- CHAT ROUTES (SESSION BASED) ---

@comprof_controller.route('/api/chat/send', methods=['POST'])
def comprof_send_chat():
    data = request.get_json()
    message = data.get('message')
    
    user_id = None
    guest_name = None
    guest_email = None
    
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
        cur = conn.cursor(dictionary=True)
        
        # 1. Cek apakah sudah ada SESSION aktif untuk user/guest ini
        session_id = None
        if user_id:
            cur.execute("SELECT id FROM chat_sessions WHERE user_id = %s LIMIT 1", (user_id,))
        else:
            cur.execute("SELECT id FROM chat_sessions WHERE guest_email = %s LIMIT 1", (guest_email,))
            
        existing_session = cur.fetchone()
        
        if existing_session:
            # Update sesi yang ada
            session_id = existing_session['id']
            cur.execute("""
                UPDATE chat_sessions 
                SET last_message = %s, last_message_at = NOW(), status = 'active'
                WHERE id = %s
            """, (message, session_id))
        else:
            # Buat sesi baru
            cur.execute("""
                INSERT INTO chat_sessions (user_id, guest_email, guest_name, last_message, last_message_at, status)
                VALUES (%s, %s, %s, %s, NOW(), 'active')
            """, (user_id, guest_email, guest_name, message))
            session_id = cur.lastrowid

        # 2. Masukkan pesan ke tabel messages dengan session_id
        cur.execute("""
            INSERT INTO chat_messages 
            (session_id, user_id, guest_name, guest_email, message, message_type, created_at, status) 
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), 'unread')
        """, (session_id, user_id, guest_name, guest_email, message, message_type))
        
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
    user_id = None
    guest_email = None
    
    if current_user.is_authenticated:
        user_id = current_user.id
    else:
        guest_email = request.args.get('guest_email')
        if not guest_email:
            return jsonify({'success': True, 'messages': []})

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'})

    messages = []
    try:
        cur = conn.cursor(dictionary=True)
        
        # Cari Session ID dulu
        session_query = ""
        session_param = ()
        
        if user_id:
            session_query = "SELECT id FROM chat_sessions WHERE user_id = %s LIMIT 1"
            session_param = (user_id,)
        else:
            session_query = "SELECT id FROM chat_sessions WHERE guest_email = %s LIMIT 1"
            session_param = (guest_email,)
            
        cur.execute(session_query, session_param)
        session_data = cur.fetchone()
        
        if session_data:
            session_id = session_data['id']
            # Ambil pesan berdasarkan Session ID
            cur.execute("""
                SELECT message, message_type, created_at 
                FROM chat_messages 
                WHERE session_id = %s 
                ORDER BY created_at ASC
            """, (session_id,))
            messages = cur.fetchall()
            
        cur.close()
        
    except mysql.connector.Error as e:
        print(f"Error fetching chat history: {e}")
    finally:
        conn.close()

    return jsonify({'success': True, 'messages': messages})