import os
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from utils.database import get_db_connection
from datetime import datetime
import mysql.connector

eggmin_controller = Blueprint('eggmin_controller', __name__)

@eggmin_controller.route('/')
@login_required
def eggmin():
    """EggMin admin dashboard - Admin only"""
    if current_user.role != 'admin':
        flash('Hanya Admin yang dapat mengakses EggMin.', 'error')
        return redirect(url_for('comprof_controller.comprof_beranda'))
    
    # Get stats for admin dashboard
    conn = get_db_connection()
    stats = {
        'system_status': 'Operational',
        'uptime': '99.9%', # Placeholder (requires server start time tracking to be real)
        'latency': '24ms'
    }
    
    last_registered_user = None
    recent_chats = []
    
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            
            # --- 1. USER STATS ---
            # Total Users
            cur.execute("SELECT COUNT(*) as count FROM users")
            stats['total_users'] = cur.fetchone()['count']
            
            # Last Registered User
            cur.execute("SELECT name, created_at FROM users ORDER BY created_at DESC LIMIT 1")
            last_registered_user = cur.fetchone()
            
            # Note: 'Last Login' requires a 'last_login' column in your users table. 
            # Since we don't have it yet, we'll leave this as None or mock it.
            stats['last_login_user'] = "Data tidak tersedia" 
            stats['last_login_time'] = None

            # --- 2. NEWS STATS ---
            # Published Count
            cur.execute("SELECT COUNT(*) as count FROM news WHERE is_published = 1")
            stats['news_published'] = cur.fetchone()['count']
            
            # Draft Count
            cur.execute("SELECT COUNT(*) as count FROM news WHERE is_published = 0")
            stats['news_draft'] = cur.fetchone()['count']
            
            # Last Published Date
            cur.execute("SELECT published_at FROM news WHERE is_published = 1 ORDER BY published_at DESC LIMIT 1")
            res_last_pub = cur.fetchone()
            stats['last_news_publish'] = res_last_pub['published_at'] if res_last_pub else None
            
            # --- 3. CHAT STATS ---
            # Unread Count
            cur.execute("SELECT COUNT(*) as count FROM chat_messages WHERE status = 'unread'")
            stats['unread_chats'] = cur.fetchone()['count']
            
            # 3 Recent Chats to Admin (incoming)
            cur.execute("""
                SELECT message, created_at, 
                       COALESCE(guest_name, 'User') as sender_name 
                FROM chat_messages 
                WHERE message_type IN ('user_to_admin', 'guest_to_admin') 
                ORDER BY created_at DESC LIMIT 3
            """)
            recent_chats = cur.fetchall()
            
            cur.close()
        except mysql.connector.Error as e:
            print(f"Error fetching stats: {e}")
        finally:
            if conn:
                conn.close()
    
    return render_template('eggmin/index.html', 
                           stats=stats, 
                           last_registered_user=last_registered_user,
                           recent_chats=recent_chats,
                           active_menu='dashboard',
                           now=datetime.now())

@eggmin_controller.route('/users')
@login_required
def eggmin_users():
    """User management page - Admin only"""
    if current_user.role != 'admin':
        flash('Hanya Admin yang dapat mengakses halaman users.', 'error')
        return redirect(url_for('comprof_controller.comprof_beranda'))
    
    # Get all users from database
    conn = get_db_connection()
    users = []
    
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM users ORDER BY created_at DESC")
            users = cur.fetchall()
            cur.close()
        except mysql.connector.Error as e:
            print(f"Error fetching users: {e}")
        finally:
            if conn:
                conn.close()
    
    return render_template('eggmin/users.html', 
                         users=users,
                         active_menu='users',
                         now=datetime.now())

@eggmin_controller.route('/news')
@login_required
def eggmin_news():
    """News management page - Admin only"""
    if current_user.role != 'admin':
        flash('Hanya Admin yang dapat mengakses halaman berita.', 'error')
        return redirect(url_for('comprof_controller.comprof_beranda'))
    
    # Get all news from database
    conn = get_db_connection()
    news_list = []
    
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM news ORDER BY created_at DESC")
            news_list = cur.fetchall()
            cur.close()
        except mysql.connector.Error as e:
            print(f"Error fetching news: {e}")
        finally:
            if conn:
                conn.close()
    
    return render_template('eggmin/news.html', 
                         news_list=news_list,
                         active_menu='news',
                         now=datetime.now())

@eggmin_controller.route('/chats')
@login_required
def eggmin_chats():
    """Chat management page with filters"""
    if current_user.role != 'admin':
        flash('Hanya Admin yang dapat mengakses halaman chat.', 'error')
        return redirect(url_for('comprof_controller.comprof_beranda'))
    
    # Ambil parameter filter dari URL
    filter_role = request.args.get('role', 'all')     # all, pembeli, pengusaha, guest
    filter_status = request.args.get('status', 'all') # all, unread, archived
    search_query = request.args.get('q', '').strip()

    conn = get_db_connection()
    conversations = []
    
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            
            # Base Query
            query = '''
                SELECT cs.id as conversation_id, 
                       COALESCE(u.name, cs.guest_name) as name,
                       COALESCE(u.email, cs.guest_email) as email,
                       CASE WHEN cs.user_id IS NOT NULL THEN u.role ELSE 'guest' END as role,
                       cs.last_message,
                       cs.last_message_at as last_message_time,
                       cs.is_pinned,
                       cs.is_archived,
                       (
                           SELECT COUNT(*) FROM chat_messages cm 
                           WHERE cm.session_id = cs.id 
                           AND cm.status = 'unread' 
                           AND cm.message_type != 'admin_to_user'
                       ) as unread_count
                FROM chat_sessions cs
                LEFT JOIN users u ON cs.user_id = u.id
                WHERE 1=1
            '''
            params = []

            # Filter by Role
            if filter_role != 'all':
                if filter_role == 'guest':
                    query += " AND cs.user_id IS NULL"
                else:
                    query += " AND u.role = %s"
                    params.append(filter_role)

            # Filter by Status (Archived vs Active)
            if filter_status == 'archived':
                query += " AND cs.is_archived = TRUE"
            else:
                query += " AND cs.is_archived = FALSE" # Default tampilkan yang tidak di-archive

            # Filter by Search (Name or Email)
            if search_query:
                query += " AND (COALESCE(u.name, cs.guest_name) LIKE %s OR COALESCE(u.email, cs.guest_email) LIKE %s)"
                params.extend([f"%{search_query}%", f"%{search_query}%"])

            # Filter Unread Only (Logika di having atau subquery, tapi untuk simpel kita filter di Python atau tambah kondisi unread > 0)
            # Jika filter_status == 'unread', kita tambahkan kondisi di bawah.
            
            # Sorting: Pinned first, then Unread messages, then Most Recent
            query += '''
                ORDER BY 
                cs.is_pinned DESC, 
                last_message_time DESC
            '''

            cur.execute(query, tuple(params))
            all_rows = cur.fetchall()
            
            # Manual filtering for 'unread' status if requested (karena unread_count adalah subquery)
            if filter_status == 'unread':
                conversations = [c for c in all_rows if c['unread_count'] > 0]
            else:
                conversations = all_rows

            cur.close()
        except mysql.connector.Error as e:
            print(f"Error fetching chats: {e}")
        finally:
            conn.close()
    
    return render_template('eggmin/chats.html', 
                           conversations=conversations,
                           active_menu='chats',
                           current_filters={
                               'role': filter_role,
                               'status': filter_status,
                               'q': search_query
                           },
                           now=datetime.now())

# ==================== API ROUTES UNTUK CHAT ADMIN ====================

@eggmin_controller.route('/api/chats/action/<string:action>/<int:session_id>', methods=['POST'])
@login_required
def eggmin_api_chat_action(action, session_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'DB Error'}), 500

    try:
        cur = conn.cursor()
        
        if action == 'pin':
            # Toggle Pin
            cur.execute("UPDATE chat_sessions SET is_pinned = NOT is_pinned WHERE id = %s", (session_id,))
            msg = "Status Pin diperbarui"
            
        elif action == 'archive':
            # Toggle Archive
            cur.execute("UPDATE chat_sessions SET is_archived = NOT is_archived WHERE id = %s", (session_id,))
            msg = "Status Arsip diperbarui"
            
        elif action == 'delete':
            # Delete session and all related messages
            cur.execute("DELETE FROM chat_messages WHERE session_id = %s", (session_id,))
            cur.execute("DELETE FROM chat_sessions WHERE id = %s", (session_id,))
            msg = "Percakapan berhasil dihapus"
            
        else:
            return jsonify({'success': False, 'error': 'Invalid action'}), 400

        conn.commit()
        cur.close()
        return jsonify({'success': True, 'message': msg})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()

@eggmin_controller.route('/api/chats/history/<int:session_id>', methods=['GET'])
@login_required
def eggmin_api_chat_history(session_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    conn = get_db_connection()
    messages = []
    try:
        cur = conn.cursor(dictionary=True)
        
        # Ambil pesan berdasarkan session_id
        cur.execute("""
            SELECT id, message, message_type, created_at, status 
            FROM chat_messages 
            WHERE session_id = %s 
            ORDER BY created_at ASC
        """, (session_id,))
        
        raw_messages = cur.fetchall()
        
        # Format waktu dan masukkan ke list
        for msg in raw_messages:
            if msg['created_at']:
                msg['created_at'] = msg['created_at'].strftime('%d %b %Y %H:%M')
            messages.append(msg)
            
        # Tandai semua pesan user/guest di sesi ini sebagai 'read'
        cur.execute("""
            UPDATE chat_messages 
            SET status='read' 
            WHERE session_id=%s AND message_type != 'admin_to_user'
        """, (session_id,))
        
        conn.commit()
        cur.close()
        
        return jsonify({'success': True, 'messages': messages})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()

@eggmin_controller.route('/api/chats/reply/<int:session_id>', methods=['POST'])
@login_required
def eggmin_api_chat_reply(session_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
    message_text = request.form.get('message')
    if not message_text:
        return jsonify({'success': False, 'error': 'Pesan kosong'}), 400

    conn = get_db_connection()
    try:
        cur = conn.cursor(dictionary=True)
        
        # Ambil info user/guest dari sesi untuk mengisi kolom redundan di chat_messages (jika perlu)
        cur.execute("SELECT user_id, guest_email, guest_name FROM chat_sessions WHERE id = %s", (session_id,))
        session_data = cur.fetchone()
        
        if not session_data:
            return jsonify({'success': False, 'error': 'Sesi tidak ditemukan'}), 404

        # Insert balasan Admin
        cur.execute("""
            INSERT INTO chat_messages 
            (session_id, user_id, guest_name, guest_email, message, message_type, created_at, status)
            VALUES (%s, %s, %s, %s, %s, 'admin_to_user', NOW(), 'read')
        """, (session_id, session_data['user_id'], session_data['guest_name'], session_data['guest_email'], message_text))
        
        # Update last message di tabel sesi
        cur.execute("""
            UPDATE chat_sessions 
            SET last_message = %s, last_message_at = NOW() 
            WHERE id = %s
        """, (message_text, session_id))
        
        conn.commit()
        cur.close()
        
        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# ==================== EGGMIN API ROUTES ====================

# Users Management APIs
@eggmin_controller.route('/api/users/create', methods=['POST'])
@login_required
def eggmin_api_users_create():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        
        if not all([name, email, password, role]):
            return jsonify({'success': False, 'error': 'Semua field harus diisi'}), 400
        
        # Validate email format
        if '@' not in email:
            return jsonify({'success': False, 'error': 'Format email tidak valid'}), 400
        
        # Validate password length
        if len(password) < 6:
            return jsonify({'success': False, 'error': 'Password harus minimal 6 karakter'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            
            # Check if email already exists
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                return jsonify({'success': False, 'error': 'Email sudah terdaftar'}), 400
            
            # Hash password and create user
            hashed_password = generate_password_hash(password)
            
            cur.execute(
                "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                (name, email, hashed_password, role)
            )
            conn.commit()
            user_id = cur.lastrowid
            cur.close()
            
            return jsonify({'success': True, 'message': 'User berhasil dibuat', 'user_id': user_id})
            
        except mysql.connector.Error as e:
            print(f"Database error in user create: {e}")
            return jsonify({'success': False, 'error': 'Database error'}), 500
        finally:
            if conn:
                conn.close()
                
    except Exception as e:
        print(f"Error in user create: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@eggmin_controller.route('/api/users/<int:user_id>', methods=['GET'])
@login_required
def eggmin_api_users_get(user_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500
    
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, name, email, role, created_at FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        cur.close()
        
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        return jsonify({'success': True, 'user': user})
        
    except mysql.connector.Error as e:
        print(f"Database error in user get: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500
    finally:
        if conn:
            conn.close()

@eggmin_controller.route('/api/users/update/<int:user_id>', methods=['POST'])
@login_required
def eggmin_api_users_update(user_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        name = request.form.get('name')
        email = request.form.get('email')
        role = request.form.get('role')
        
        if not all([name, email, role]):
            return jsonify({'success': False, 'error': 'All fields are required'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            
            # Check if user exists and not current user
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user = cur.fetchone()
            if not user:
                return jsonify({'success': False, 'error': 'User not found'}), 404
            
            # Check if email already exists for other users
            cur.execute("SELECT id FROM users WHERE email = %s AND id != %s", (email, user_id))
            if cur.fetchone():
                return jsonify({'success': False, 'error': 'Email already exists'}), 400
            
            cur.execute(
                "UPDATE users SET name = %s, email = %s, role = %s WHERE id = %s",
                (name, email, role, user_id)
            )
            conn.commit()
            cur.close()
            
            return jsonify({'success': True, 'message': 'User updated successfully'})
            
        except mysql.connector.Error as e:
            print(f"Database error in user update: {e}")
            return jsonify({'success': False, 'error': 'Database error'}), 500
        finally:
            if conn:
                conn.close()
                
    except Exception as e:
        print(f"Error in user update: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@eggmin_controller.route('/api/users/delete/<int:user_id>', methods=['POST'])
@login_required
def eggmin_api_users_delete(user_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    # Prevent self-deletion
    if user_id == current_user.id:
        return jsonify({'success': False, 'error': 'Cannot delete your own account'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500
    
    try:
        cur = conn.cursor()
        
        # Check if user exists
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        if not cur.fetchone():
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        cur.close()
        
        return jsonify({'success': True, 'message': 'User deleted successfully'})
        
    except mysql.connector.Error as e:
        print(f"Database error in user delete: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500
    finally:
        if conn:
            conn.close()

# News Management APIs
@eggmin_controller.route('/api/news/create', methods=['POST'])
@login_required
def eggmin_api_news_create():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        title = request.form.get('title')
        content = request.form.get('content')
        image_url = request.form.get('image_url')
        is_published = request.form.get('is_published') == 'on'
        
        # Handle File Upload
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                # Generate timestamp to avoid dupes
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                new_filename = f"{timestamp}_{filename}"
                
                # Ensure dir exists
                save_path = os.path.join(current_app.root_path, 'static', 'uploads', 'news')
                os.makedirs(save_path, exist_ok=True)
                
                file.save(os.path.join(save_path, new_filename))
                image_url = url_for('static', filename=f'uploads/news/{new_filename}')

        if not title or not content:
            return jsonify({'success': False, 'error': 'Title and content are required'}), 400
        
        conn = get_db_connection()
        # ... (sisa kode sama seperti sebelumnya: koneksi DB, insert ke DB, commit) ...
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            published_at = datetime.now() if is_published else None
            
            cur.execute(
                "INSERT INTO news (title, content, image_url, is_published, published_at) VALUES (%s, %s, %s, %s, %s)",
                (title, content, image_url, is_published, published_at)
            )
            conn.commit()
            news_id = cur.lastrowid
            cur.close()
            
            return jsonify({'success': True, 'message': 'News created successfully', 'news_id': news_id})
        except mysql.connector.Error as e:
            print(f"Database error: {e}")
            return jsonify({'success': False, 'error': 'Database error'}), 500
        finally:
            if conn: conn.close()
                
    except Exception as e:
        print(f"Error in news create: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@eggmin_controller.route('/api/news/<int:news_id>', methods=['GET'])
@login_required
def eggmin_api_news_get(news_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500
    
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM news WHERE id = %s", (news_id,))
        news = cur.fetchone()
        cur.close()
        
        if not news:
            return jsonify({'success': False, 'error': 'News not found'}), 404
        
        # Convert datetime to string for JSON serialization
        if news['published_at']:
            news['published_at'] = news['published_at'].strftime('%Y-%m-%d %H:%M:%S')
        if news['created_at']:
            news['created_at'] = news['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            
        return jsonify({'success': True, 'news': news})
        
    except mysql.connector.Error as e:
        print(f"Database error in news get: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500
    finally:
        if conn:
            conn.close()

@eggmin_controller.route('/api/news/update/<int:news_id>', methods=['POST'])
@login_required
def eggmin_api_news_update(news_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        title = request.form.get('title')
        content = request.form.get('content')
        image_url = request.form.get('image_url') # Gets the URL text input
        is_published = request.form.get('is_published') == 'on'
        
        # Handle File Upload (Priority over URL input)
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                new_filename = f"{timestamp}_{filename}"
                
                save_path = os.path.join(current_app.root_path, 'static', 'uploads', 'news')
                os.makedirs(save_path, exist_ok=True)
                
                file.save(os.path.join(save_path, new_filename))
                image_url = url_for('static', filename=f'uploads/news/{new_filename}')
        
        if not title or not content:
            return jsonify({'success': False, 'error': 'Judul dan konten berita harus diisi'}), 400
        
        conn = get_db_connection()
        # ... (sisa kode update database sama seperti sebelumnya) ...
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            # Check existing...
            cur.execute("SELECT * FROM news WHERE id = %s", (news_id,))
            if not cur.fetchone():
                return jsonify({'success': False, 'error': 'Berita tidak ditemukan'}), 404
            
            # Update Status Logic...
            cur.execute("SELECT is_published, published_at FROM news WHERE id = %s", (news_id,))
            current_data = cur.fetchone()
            current_status = current_data[0]
            current_published_at = current_data[1]
            
            published_at = current_published_at
            if is_published and not current_status:
                published_at = datetime.now()
            elif not is_published:
                published_at = None
            
            # Update Query
            cur.execute(
                "UPDATE news SET title = %s, content = %s, image_url = %s, is_published = %s, published_at = %s WHERE id = %s",
                (title, content, image_url, is_published, published_at, news_id)
            )
                
            conn.commit()
            cur.close()
            
            return jsonify({'success': True, 'message': 'Berita berhasil diperbarui'})
            
        except mysql.connector.Error as e:
            print(f"Database error: {e}")
            return jsonify({'success': False, 'error': 'Database error'}), 500
        finally:
            if conn: conn.close()

    except Exception as e:
        print(f"Error in news update: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@eggmin_controller.route('/api/news/toggle-publish/<int:news_id>', methods=['POST'])
@login_required
def eggmin_api_news_toggle_publish(news_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500
    
    try:
        cur = conn.cursor(dictionary=True)
        
        # Get current status
        cur.execute("SELECT is_published FROM news WHERE id = %s", (news_id,))
        result = cur.fetchone()
        if not result:
            return jsonify({'success': False, 'error': 'Berita tidak ditemukan'}), 404
        
        current_status = result['is_published']
        new_status = not current_status
        published_at = datetime.now() if new_status else None
        
        cur.execute(
            "UPDATE news SET is_published = %s, published_at = %s WHERE id = %s",
            (new_status, published_at, news_id)
        )
            
        conn.commit()
        cur.close()
        
        action = "dipublikasikan" if new_status else "disimpan sebagai draft"
        return jsonify({'success': True, 'message': f'Berita berhasil {action}', 'new_status': new_status})
        
    except mysql.connector.Error as e:
        print(f"Database error in news toggle: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500
    finally:
        if conn:
            conn.close()

@eggmin_controller.route('/api/news/delete/<int:news_id>', methods=['POST'])
@login_required
def eggmin_api_news_delete(news_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500
    
    try:
        cur = conn.cursor()
        
        # Check if news exists
        cur.execute("SELECT * FROM news WHERE id = %s", (news_id,))
        if not cur.fetchone():
            return jsonify({'success': False, 'error': 'Berita tidak ditemukan'}), 404
        
        cur.execute("DELETE FROM news WHERE id = %s", (news_id,))
        conn.commit()
        cur.close()
        
        return jsonify({'success': True, 'message': 'Berita berhasil dihapus'})
        
    except mysql.connector.Error as e:
        print(f"Database error in news delete: {e}")
        return jsonify({'success': False, 'error': 'Database error'}), 500
    finally:
        if conn:
            conn.close()