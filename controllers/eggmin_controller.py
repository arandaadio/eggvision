from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
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
    stats = {}
    recent_users = []
    
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            
            # Get user counts
            cur.execute("SELECT COUNT(*) as count FROM users")
            stats['total_users'] = cur.fetchone()['count']
            
            cur.execute("SELECT COUNT(*) as count FROM users WHERE role = 'pembeli'")
            stats['pembeli_count'] = cur.fetchone()['count']
            
            cur.execute("SELECT COUNT(*) as count FROM users WHERE role = 'pengusaha'")
            stats['pengusaha_count'] = cur.fetchone()['count']
            
            cur.execute("SELECT COUNT(*) as count FROM users WHERE role = 'admin'")
            stats['admin_count'] = cur.fetchone()['count']
            
            # Get product counts
            cur.execute("SELECT COUNT(*) as count FROM products")
            stats['total_products'] = cur.fetchone()['count']
            
            # Get news counts
            cur.execute("SELECT COUNT(*) as count FROM news")
            stats['total_news'] = cur.fetchone()['count']
            
            # Get unread chat count
            cur.execute("SELECT COUNT(*) as count FROM chat_messages WHERE status = 'unread'")
            stats['unread_chats'] = cur.fetchone()['count']
            
            # Get recent users
            cur.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT 5")
            recent_users = cur.fetchall()
            
            cur.close()
        except mysql.connector.Error as e:
            print(f"Error fetching stats: {e}")
        finally:
            if conn:
                conn.close()
    
    return render_template('eggmin/index.html', 
                         stats=stats, 
                         recent_users=recent_users,
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

@eggmin_controller.route('/products')
@login_required
def eggmin_products():
    """Product management page - Admin only"""
    if current_user.role != 'admin':
        flash('Hanya Admin yang dapat mengakses halaman produk.', 'error')
        return redirect(url_for('comprof_controller.comprof_beranda'))
    
    # Get all products with user info
    conn = get_db_connection()
    products = []
    
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute('''
                SELECT p.*, u.name as seller_name, u.email as seller_email
                FROM products p 
                LEFT JOIN users u ON p.user_id = u.id
                ORDER BY p.created_at DESC
            ''')
            products = cur.fetchall()
            cur.close()
        except mysql.connector.Error as e:
            print(f"Error fetching products: {e}")
        finally:
            if conn:
                conn.close()
    
    return render_template('eggmin/products.html', 
                         products=products,
                         active_menu='products',
                         now=datetime.now())

@eggmin_controller.route('/chats')
@login_required
def eggmin_chats():
    """Chat management page - Admin only"""
    if current_user.role != 'admin':
        flash('Hanya Admin yang dapat mengakses halaman chat.', 'error')
        return redirect(url_for('comprof_controller.comprof_beranda'))
    
    # Get all chat messages with user info
    conn = get_db_connection()
    chat_messages = []
    
    if conn:
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute('''
                SELECT cm.*, 
                       COALESCE(u.name, cm.guest_name) as sender_name,
                       COALESCE(u.email, cm.guest_email) as sender_email,
                       COALESCE(u.role, 'guest') as sender_role
                FROM chat_messages cm
                LEFT JOIN users u ON cm.user_id = u.id
                ORDER BY cm.created_at DESC
                LIMIT 100
            ''')
            chat_messages = cur.fetchall()
            cur.close()
        except mysql.connector.Error as e:
            print(f"Error fetching chat messages: {e}")
        finally:
            if conn:
                conn.close()
    
    return render_template('eggmin/chats.html', 
                         chat_messages=chat_messages,
                         active_menu='chats',
                         now=datetime.now())

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
        
        if not title or not content:
            return jsonify({'success': False, 'error': 'Title and content are required'}), 400
        
        conn = get_db_connection()
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
            print(f"Database error in news create: {e}")
            return jsonify({'success': False, 'error': 'Database error'}), 500
        finally:
            if conn:
                conn.close()
                
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
        image_url = request.form.get('image_url')
        is_published = request.form.get('is_published') == 'on'
        
        if not title or not content:
            return jsonify({'success': False, 'error': 'Judul dan konten berita harus diisi'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        try:
            cur = conn.cursor()
            
            # Check if news exists
            cur.execute("SELECT * FROM news WHERE id = %s", (news_id,))
            if not cur.fetchone():
                return jsonify({'success': False, 'error': 'Berita tidak ditemukan'}), 404
            
            # Get current published status
            cur.execute("SELECT is_published, published_at FROM news WHERE id = %s", (news_id,))
            current_data = cur.fetchone()
            current_status = current_data[0]
            current_published_at = current_data[1]
            
            published_at = current_published_at
            if is_published and not current_status:
                # If changing from draft to published, set published_at to now
                published_at = datetime.now()
            elif not is_published:
                # If unpublishing, set published_at to None
                published_at = None
            
            cur.execute(
                "UPDATE news SET title = %s, content = %s, image_url = %s, is_published = %s, published_at = %s WHERE id = %s",
                (title, content, image_url, is_published, published_at, news_id)
            )
                
            conn.commit()
            cur.close()
            
            return jsonify({'success': True, 'message': 'Berita berhasil diperbarui'})
            
        except mysql.connector.Error as e:
            print(f"Database error in news update: {e}")
            return jsonify({'success': False, 'error': 'Database error'}), 500
        finally:
            if conn:
                conn.close()
                
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